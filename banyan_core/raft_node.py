import asyncio
from config import NODE_ROLES, KAFKA_TOPICS
from httpx import AsyncClient
from datetime import datetime, timezone
from models import (RequestVoteRequest,
                    RequestVoteResponse,
                    LogEntry,
                    AppendEntriesRequest,
                    AppendEntriesResponse,
                    HeartBeatRequest,
                    HeartBeatResponse,
                    LeaderAnnouncementRequest,
                    LeaderAnnouncementResponse,
                    LeaderConsensusResponse)
from store import Store
import random
from collections import Counter
from banyan_core_logger import BanyanCoreLogger



class RaftNode:
    def __init__(self, node_id:str, logger:BanyanCoreLogger=None):
        self.node_id = node_id
        self.curr_role = NODE_ROLES["FOLLOWER"]

        self.store = Store()

        self.current_leader = None
        self.current_term = 0
        self.voted_for = None
        self.log = []

        self.commit_index = -1
        self.last_applied = -1

        self.next_index = {}
        self.match_index = {}

        self.peers = {}
        self.votes_received = 0

        self.heartbeat_task = None
        self.max_wait = 15 # 15 secs wait before marking node dead

        self.is_election = False

        self.rootkeeper = None

        self.logger = logger
    
    async def handle_request_vote(self, req: RequestVoteRequest):
        if self.curr_role == NODE_ROLES["ROOTKEEPER"]:
            return RequestVoteResponse(
                    vote_granted=False,
                    term = self.current_term
                )

        # Step 1: if candidates term is less than my current term,
        # reject vote
        self.is_election = True
        if req.term < self.current_term:
            return RequestVoteResponse(vote_granted=False,
                                       term=self.current_term)

        # Step 2: If candidates term is greater than my current term,
        # update my term and become follower
        self.current_term = req.term
        return await self.become_follower(req.term, req.candidate_id)

    async def handle_append_entries(self, req: AppendEntriesRequest):
        for entry in req.entries:
            cmd = entry.command
            if cmd["type"] == "SET":
                self.store.add_record(cmd["key"], cmd["value"])
            elif cmd["type"] == "DELETE":
                self.store.delete_record(cmd["key"])
            elif cmd["type"] == "COMMIT":
                log_msg = f"[COMMIT] Received commit for {cmd['key']}"
                
                await self.logger.log(KAFKA_TOPICS["STORE_TOPIC"],log_msg)
                self.store.commit_record(cmd["key"])
            else:
                log_msg = f"[UNKNOWN CMD] {cmd['type']}"
                
                await self.logger.log(KAFKA_TOPICS["STORE_TOPIC"],log_msg)

            self.log.append(entry)  # entry is already a LogEntry
        return AppendEntriesResponse(term=self.current_term, success=True)

    async def become_follower(self, term, candidate_id):
        self.curr_role = NODE_ROLES["FOLLOWER"]
        self.current_term = term
        self.voted_for = candidate_id

        for peer in self.peers:
            # TODO: this logic fails when multiple elections started
            if peer == candidate_id:
                self.peers[peer]["role"] = NODE_ROLES["CANDIDATE"]
            else:
                self.peers[peer]["role"] = NODE_ROLES["FOLLOWER"]

        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None
        
        return RequestVoteResponse(
                    vote_granted=True,
                    term = self.current_term
                )

    async def become_leader(self):
        last_index = len(self.log)
        self.current_leader = self.node_id

        ack_count = 0

        async with AsyncClient() as client:
            for peer in self.peers:
                self.next_index[peer] = last_index
                self.match_index[peer] = -1
            
                # broadcast leadership
                try:
                    req = LeaderAnnouncementRequest(
                        term=self.current_term,
                        leader_id=self.node_id
                    )
                    # use single quotes inside f-string
                    resp = await client.post(f"""{self.peers[peer]["peer_url"]}/leader-announcement""", json=req.dict())
                    data = resp.json()
                    
                    # mark node alive
                    if resp.status_code == 200:
                        self.peers[peer]["last_seen"] = str(datetime.now(timezone.utc).timestamp())

                    # may be mark as alive?
                    if self.peers[peer]["role"] != NODE_ROLES["ROOTKEEPER"]:
                        if data["ack"] is True:
                            ack_count += 1

                except Exception as e:
                    log_msg = f"[LEADER_ACK] Failed to reach {peer}: {e}"
                    
                    await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

        valid_voter_count = 0
        for voter in self.peers:
            if self.peers[voter]["role"] != NODE_ROLES["ROOTKEEPER"]:
                # this is a valid voter
                valid_voter_count+=1
        
        majority = (valid_voter_count + 1)//2

        if ack_count > majority:
            # declare self as leader
            self.curr_role = NODE_ROLES["LEADER"]
            # mark others as followers
            for peer in self.peers:
                if self.peers[peer]["role"] != NODE_ROLES["ROOTKEEPER"]:
                    self.peers[peer]["role"] = NODE_ROLES["FOLLOWER"]
            
            self.is_election = False

            if self.heartbeat_task:
                self.heartbeat_task.cancel()
            self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())

    async def become_candidate(self):
        self.curr_role = NODE_ROLES["CANDIDATE"]
        self.current_term += 1
        self.voted_for = self.node_id
        self.votes_received = 1

        req = RequestVoteRequest(
            term=self.current_term,
            candidate_id=self.node_id,
            last_log_index=len(self.log) - 1,
            last_log_term=self.log[-1].term if self.log else 0
        )

        self.is_election = True
        async with AsyncClient() as client:
            for peer, val in self.peers.items():
                if val["role"] == NODE_ROLES["ROOTKEEPER"]:
                    continue
                else:
                    try:
                        resp = await client.post(f"{val['peer_url']}/request-vote", json=req.dict())
                        data = resp.json()
                        log_msg = None
                        if data.get("vote_granted") is True:
                            self.votes_received += 1
                            log_msg = f"[VOTE] {peer} voted"
                            
                            await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)
                        else:
                            log_msg = f"[VOTE] {peer} rejected vote"
                            
                            await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)
                    except Exception as e:
                        log_msg = f"[CANDIDATE] Failed to reach {peer}: {e}"
                        
                        await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

        valid_voter_count = 0
        for voter in self.peers:
            if self.peers[voter]["role"] != NODE_ROLES["ROOTKEEPER"]:
                # this is a valid voter
                valid_voter_count+=1
        
        majority = (valid_voter_count + 1)//2

        if self.votes_received >= majority:
            await self.become_leader()

    async def handle_leader_ack(self, req: LeaderAnnouncementRequest):
        log_msg = f"[LEADER_ANNOUNCE] Received from {req.leader_id} at node {self.node_id}"
        
        await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)


        self.current_leader = req.leader_id
        self.voted_for = None
        self.is_election = False

        if req.leader_id in self.peers:
            self.peers[req.leader_id]["role"] = NODE_ROLES["LEADER"]
            self.peers[req.leader_id]["last_seen"] = str(datetime.now(timezone.utc).timestamp())

            # mark all other nodes as followers
            for peer in self.peers:
                if self.peers[peer]["role"] not in [NODE_ROLES["LEADER"], NODE_ROLES["ROOTKEEPER"]]:
                    self.peers[peer]["role"] = NODE_ROLES["FOLLOWER"]
    
            # fetch log
            if self.node_id != req.leader_id and self.curr_role != NODE_ROLES["ROOTKEEPER"]:
                self.curr_role = NODE_ROLES["FOLLOWER"]
                asyncio.create_task(self.fetch_full_log_from_leader())

        return LeaderAnnouncementResponse(
            ack=True,
            timestamp=str(datetime.now(timezone.utc).timestamp())
        )

    async def send_heartbeats(self):
        async with AsyncClient() as client:
            for peer, val in self.peers.items():
                try:
                    timestamp = datetime.now(timezone.utc).timestamp()
                    req = HeartBeatRequest(
                        node_id=self.node_id,
                        timestamp=str(timestamp)
                    )
                    # use single quotes inside f-string
                    resp = await client.post(f"""{val["peer_url"]}/ping""", json=req.dict())
                    data = resp.json()

                    # print("++++++++++++++++++++++++")
                    log_msg = f"[PING ACK] {peer} | {data}"
                    
                    await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

                    if data.get("ack", None):
                        self.peers[peer]["is_alive"] = True
                    else:
                        self.peers[peer]["is_alive"] = False

                except Exception as e:
                    log_msg = f"[HEARTBEAT] Failed to reach {peer}: {e}"
                    
                    await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)
                    self.peers[peer]["is_alive"] = False

    async def handle_heartbeat(self, req: HeartBeatRequest):
        timestamp = str(datetime.now(timezone.utc).timestamp())

        if self.curr_role == NODE_ROLES["LEADER"] and req.node_id == self.rootkeeper:
            return HeartBeatResponse(ack=True, timestamp=timestamp)

        elif self.curr_role == NODE_ROLES["ROOTKEEPER"] and req.node_id == self.current_leader:
            # Rootkeeper receives heartbeat from leader
            if req.node_id in self.peers:
                self.peers[req.node_id]["is_alive"] = True
                self.peers[req.node_id]["last_seen"] = timestamp
            return HeartBeatResponse(ack=True, timestamp=timestamp)

        elif self.curr_role not in [NODE_ROLES["ROOTKEEPER"], NODE_ROLES["LEADER"]]:
            if req.node_id in [self.rootkeeper, self.current_leader]:

                if self.current_leader is None and self.rootkeeper != req.node_id:
                    self.current_leader = req.node_id
                    if self.node_id != req.node_id:
                        self.curr_role = NODE_ROLES["FOLLOWER"]
                    asyncio.create_task(self.fetch_full_log_from_leader())

                if req.node_id in self.peers:
                    self.peers[req.node_id]["is_alive"] = True
                    self.peers[req.node_id]["last_seen"] = timestamp

                return HeartBeatResponse(ack=True, timestamp=timestamp)

        return HeartBeatResponse(ack=False, timestamp=timestamp)

    async def mark_dead(self, leader_id):
        # only leader
        try:
            if leader_id not in self.peers:
                raise Exception("Node not found")
            self.peers[leader_id]["is_alive"] = False
            self.peers[leader_id]["role"] = None
            self.current_leader = None
        except Exception as e:
            log_msg = f"[PEER] Failed to mark peer as dead: {e}"
            
            await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

    async def set_rootkeeper(self, node_id):
        self.rootkeeper = node_id

    async def add_peer(self, node_id, role, peer_url):
        try:
            if node_id in self.peers:
                log_msg = f"[PEER] Peer {node_id} already exists"
                
                await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)
                return

            timestamp = datetime.now(timezone.utc).timestamp()

            self.peers[node_id] = {
                "peer_url": peer_url,
                "is_alive": True,
                "last_seen": timestamp,
                "role": role
            }

            log_msg = f"new_node: {self.peers[node_id]}"
            
            await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

        except Exception as e:
            log_msg = f"[PEER] Failed to add peer: {e}"
            
            await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

    async def remove_peer(self, node_id):
        try:
            if node_id not in self.peers:
                raise Exception("Node not found")
            del self.peers[node_id]

        except Exception as e:
            log_msg = f"[PEER] Failed to remove peer: {e}"
            
            await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)
    
    async def election_timeout_loop(self):
        while True:
            timeout = random.uniform(5, 20)
            await asyncio.sleep(timeout)

            if self.curr_role == NODE_ROLES["ROOTKEEPER"]:
                return

            if self.curr_role != NODE_ROLES["LEADER"] and \
                (self.current_leader is None or
                 self.peers.get(self.current_leader, None) is None or
                 self.peers.get(self.current_leader, None).get("is_alive", None) is None):

                log_msg = f"[TIMEOUT] Node {self.node_id} starting election for term {self.current_term + 1}"
                
                await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

                await self.become_candidate()

                # add buffer to avoid back-to-back elections
                await asyncio.sleep(5)

    async def heartbeat_timeout_loop(self):
        while True:
            await asyncio.sleep(5)
           
            if self.curr_role == NODE_ROLES["LEADER"]:
                continue  # Leaders don’t track leaders

            if not self.current_leader or self.current_leader not in self.peers:
                continue  # No valid leader to check against

            try:
                curr_timestamp = datetime.now(timezone.utc).timestamp()
                last_seen = float(self.peers[self.current_leader].get("last_seen", 0))
                delta_secs = curr_timestamp - last_seen

                log_msg = f"[CHECK] Leader: {self.current_leader}, Last Seen: {delta_secs:.2f}s ago"
                
                await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

                if delta_secs > self.max_wait:
                    log_msg = f"[TIMEOUT] Leader Node {self.current_leader} marked as dead"
                    
                    await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

                    await self.mark_dead(self.current_leader)
            except Exception as e:
                log_msg = f"[ERROR] Heartbeat timeout check failed: {e}"
                
                await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

    async def heartbeat_loop(self):
        while True:
            timeout = 5
            await asyncio.sleep(timeout)

            if self.curr_role == NODE_ROLES["LEADER"]:
                await self.send_heartbeats()

    async def rootkeeper_loop(self):
        while self.curr_role == NODE_ROLES["ROOTKEEPER"]:
            await asyncio.sleep(5)
            await self.send_heartbeats()

    async def get_cluster_state(self):
        live_node_count = 0
        for peer,state in self.peers.items():
            if state["is_alive"] is True:
                live_node_count += 1

        return {
            "leader_id": self.current_leader,
            "node_id": self.node_id,
            "role": self.curr_role,
            "current_term": self.current_term,
            "is_election": self.is_election,
            "live_node_count": live_node_count,
            "total_nodes": len(self.peers),
            "peers": self.peers
        }

    def handle_client_write(self, key, value):
        self.store.add_record(key, value)

        new_log_entry = LogEntry(
            term=self.current_term,
            command={
                "type": "SET",
                "key": key,
                "value": value
            },
            index=len(self.log),
            committed=False
        )

        self.log.append(new_log_entry)
        asyncio.create_task(self.replicate_and_commit(new_log_entry))

    async def replicate_and_commit(self, entry: LogEntry):
        success_count = 1  # include self
        async with AsyncClient() as client:
            for peer_id, peer in self.peers.items():
                if peer["role"] == NODE_ROLES["ROOTKEEPER"]:
                    continue

                try:
                    req = AppendEntriesRequest(
                        term=self.current_term,
                        leader_id=self.node_id,
                        prev_log_index=len(self.log) - 2,
                        prev_log_term=self.log[-2].term if len(self.log) > 1 else 0,
                        entries=[entry],
                        leader_commit=self.commit_index
                    )
                    resp = await client.post(f"{peer['peer_url']}/append-entries", json=req.model_dump())
                    data = resp.json()
                    if data["success"]:
                        success_count += 1
                except Exception as e:
                    log_msg = f"[LOG REPL] Failed to replicate to {peer_id}: {e}"
                    
                    await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

        if success_count > len(self.peers) // 2:
            log_msg = f"[COMMIT] Majority ack for {entry.command['type']} {entry.command['key']}"
            
            await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

            commit_entry = LogEntry(
                term=self.current_term,
                command={
                    "type": "COMMIT",
                    "key": entry.command["key"]
                },
                index=len(self.log),
                committed=True
            )
            self.log.append(commit_entry)
            self.commit_index = commit_entry.index
            self.store.commit_record(commit_entry.command["key"])
            asyncio.create_task(self.replicate_commit(commit_entry))

    async def replicate_commit(self, commit_entry: LogEntry):
        async with AsyncClient() as client:
            for peer_id, peer in self.peers.items():
                if peer["role"] == NODE_ROLES["ROOTKEEPER"]:
                    continue
                try:
                    req = AppendEntriesRequest(
                        term=self.current_term,
                        leader_id=self.node_id,
                        prev_log_index=commit_entry.index - 1,
                        prev_log_term=self.log[commit_entry.index - 1].term if commit_entry.index > 0 else 0,
                        entries=[commit_entry],
                        leader_commit=self.commit_index
                    )
                    await client.post(f"{peer['peer_url']}/append-entries", json=req.model_dump())
                except Exception as e:
                    log_msg = f"[COMMIT REPLICATE] {peer_id} failed: {e}"
                    
                    await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

    async def fetch_full_log_from_leader(self):
        if not self.current_leader:
            log_msg = "[SYNC] Skipping sync — no known leader."
            
            await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)
            return

        if self.curr_role == NODE_ROLES["ROOTKEEPER"]:
            return

        leader_url = self.peers[self.current_leader]["peer_url"]
        async with AsyncClient() as client:
            try:
                resp = await client.get(f"{leader_url}/sync-entries")

                if resp.status_code != 200:
                    log_msg = f"[SYNC] Failed with status {resp.status_code}: {resp.text}"
                    
                    await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)
                    return

                data = resp.json()
                req = AppendEntriesRequest(**data)
                await self.handle_append_entries(req)

            except Exception as e:
                log_msg = f"[SYNC] Failed to sync from leader: {e}"
                
                await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

    async def check_leadership_consensus(self):
        leader_map = Counter()
        async with AsyncClient() as client:
            for peer,val in self.peers.items():
                try:
                    resp = await client.get(f"""{val["peer_url"]}/leader-consensus""")
                    data = resp.json()

                    reported_leader = data.get("leader_id")
                    if reported_leader:
                        leader_map[reported_leader]+=1
                except Exception as e:
                    log_msg = f"[LEADER_CONSENSUS] Failed to reach {peer}: {e}"
                    
                    await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)
                    self.peers[peer]["is_alive"] = False

        log_msg = f"Leader vote counts:{leader_map}"
        
        await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

        if not leader_map:
            log_msg = "[CONSENSUS] No leader reported by peers."
            
            await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)
            return await self.force_priority_election()
    
        consensus_leader, count = leader_map.most_common(1)[0]
        if count > len(self.peers) // 2:
            log_msg = f"[CONSENSUS] Consensus leader: {consensus_leader} with {count} votes"
            
            await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)

            self.current_leader = consensus_leader
            for peer, val in self.peers.items():
                if val["role"] == NODE_ROLES["ROOTKEEPER"]:
                    continue
                val["role"] = NODE_ROLES["LEADER"] if peer == consensus_leader else NODE_ROLES["FOLLOWER"]

                if self.node_id != consensus_leader:
                    self.curr_role = NODE_ROLES["FOLLOWER"]
        else:
            log_msg = "[CONSENSUS] No majority found. Starting priority election."
            
            await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)
            await self.force_priority_election()

    async def force_priority_election(self):
        log_msg = "[PRIORITY ELECTION] Triggered due to lack of consensus."
        
        await self.logger.log(KAFKA_TOPICS["RAFT_TOPIC"],log_msg)
        await self.become_candidate()
    
    async def consensus_monitor_loop(self):
        while True:
            await asyncio.sleep(15)  # tune frequency
            if self.curr_role != NODE_ROLES["ROOTKEEPER"]:
                await self.check_leadership_consensus()

    async def get_leader(self):
        return LeaderConsensusResponse(leader_id=self.current_leader,
                                       reported_by=self.node_id,
                                       reported_at=datetime.now(timezone.utc).timestamp())
