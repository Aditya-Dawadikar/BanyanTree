import asyncio
from config import NODE_ROLES
from httpx import AsyncClient
from datetime import datetime, timezone
from peer import Peer
from models import (RequestVoteRequest,
                    RequestVoteResponse,
                    LogEntry,
                    AppendEntriesRequest,
                    AppendEntriesResponse,
                    HeartBeatRequest,
                    HeartBeatResponse,
                    LeaderAnnouncementRequest,
                    LeaderAnnouncementResponse)
from store import Store
import random



class RaftNode:
    def __init__(self, node_id:str):
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
    
    def handle_request_vote(self, req: RequestVoteRequest):
        # Step 1: if candidates term is less than my current term,
        # reject vote
        self.is_election = True
        if req.term < self.current_term:
            return RequestVoteResponse(vote_granted=False, term=self.current_term)

        # Step 2: If candidates term is greater than my current term,
        # update my term and become follower
        self.current_term = req.term
        return self.become_follower(req.term, req.candidate_id)

    def handle_append_entries(self, req: AppendEntriesRequest):
        for entry in req.entries:
            cmd = entry.command
            if cmd["type"] == "SET":
                self.store.add_record(cmd["key"], cmd["value"])
            elif cmd["type"] == "DELETE":
                self.store.delete_record(cmd["key"])
            elif cmd["type"] == "COMMIT":
                print(f"[COMMIT] Received commit for {cmd['key']}")
                self.store.commit_record(cmd["key"])
            else:
                print(f"[UNKNOWN CMD] {cmd['type']}")

            self.log.append(entry)  # entry is already a LogEntry
        return AppendEntriesResponse(term=self.current_term, success=True)

    def become_follower(self, term, candidate_id):
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
                    if data["ack"] is True:
                        ack_count += 1

                except Exception as e:
                    print(f"[LEADER_ACK] Failed to reach {peer}: {e}")

        if ack_count > len(self.peers)//2:
            # declare self as leader
            self.curr_role = NODE_ROLES["LEADER"]
            # mark others as followers
            for peer in self.peers:
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
                try:
                    resp = await client.post(f"{val['peer_url']}/request-vote", json=req.dict())
                    data = resp.json()
                    if data.get("vote_granted"):
                        self.votes_received += 1
                        print(f"[VOTE] {peer} voted")
                    else:
                        print(f"[VOTE] {peer} rejected vote")
                except Exception as e:
                    print(f"[CANDIDATE] Failed to reach {peer}: {e}")

        if self.votes_received > len(self.peers) // 2:
            await self.become_leader()

    def handle_leader_ack(self, req: LeaderAnnouncementRequest):
        self.current_leader = req.leader_id
        self.voted_for = None
        self.is_election = False

        if req.leader_id in self.peers:
            self.peers[req.leader_id]["role"] = NODE_ROLES["LEADER"]
            self.peers[req.leader_id]["last_seen"] = str(datetime.now(timezone.utc).timestamp())

            # fetch log
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

                    if data.get("ack", False):
                        self.peers[peer]["is_alive"] = True
                    else:
                        self.peers[peer]["is_alive"] = False

                except Exception as e:
                    print(f"[HEARTBEAT] Failed to reach {peer}: {e}")
                    self.peers[peer]["is_alive"] = False

    def handle_heartbeat(self, req: HeartBeatRequest):
        timestamp = str(datetime.now(timezone.utc).timestamp())

        # Accept heartbeat from any peer and update current_leader if needed
        if self.current_leader is None:
            self.current_leader = req.node_id
            asyncio.create_task(self.fetch_full_log_from_leader())

        if req.node_id == self.current_leader and req.node_id in self.peers:
            was_dead = not self.peers[req.node_id].get("is_alive", False)

            self.peers[req.node_id]["is_alive"] = True
            self.peers[req.node_id]["last_seen"] = timestamp

            if was_dead:
                print(f"[SYNC] Detected reconnection to leader {req.node_id}, syncing log")
                asyncio.create_task(self.fetch_full_log_from_leader())

            return HeartBeatResponse(ack=True, timestamp=timestamp)

        return HeartBeatResponse(ack=False, timestamp=timestamp)


    def mark_dead(self, leader_id):
        # only leader
        try:
            if leader_id not in self.peers:
                raise Exception("Node not found")
            self.peers[leader_id]["is_alive"] = False
            self.peers[leader_id]["role"] = None
            self.current_leader = None
        except Exception as e:
            print(f"[PEER] Failed to mark peer as dead: {e}")

    def add_peer(self, node_id, role, peer_url):
        try:
            if node_id in self.peers:
                print(f"[PEER] Peer {node_id} already exists")
                return

            timestamp = datetime.now(timezone.utc).timestamp()

            self.peers[node_id] = {
                "peer_url": peer_url,
                "is_alive": True,
                "last_seen": timestamp,
                "role": role
            }

            print("new_node: ", self.peers[node_id])

        except Exception as e:
            print(f"[PEER] Failed to add peer: {e}")

    def remove_peer(self, node_id):
        try:
            if node_id not in self.peers:
                raise Exception("Node not found")
            del self.peers[node_id]

        except Exception as e:
            print(f"[PEER] Failed to remove peer: {e}")
    
    async def election_timeout_loop(self):
        while True:
            timeout = random.uniform(5, 20)
            await asyncio.sleep(timeout)

            if self.curr_role != NODE_ROLES["LEADER"] and self.current_leader is None:
                print(f"[TIMEOUT] Node {self.node_id} starting election for term {self.current_term + 1}")
                await self.become_candidate()
                # add buffer to avoid back-to-back elections
                await asyncio.sleep(5)

    async def heartbeat_timeout_loop(self):
        while True:
            timeout = 5
            await asyncio.sleep(timeout)

            if self.curr_role == NODE_ROLES["LEADER"]:
                continue

            curr_timestamp = datetime.now(timezone.utc).timestamp()

            if self.current_leader and self.current_leader in self.peers:
                last_seen = float(self.peers[self.current_leader]["last_seen"])
                delta_secs = curr_timestamp - last_seen

                print(self.current_leader, delta_secs)
                if delta_secs > self.max_wait:
                    # mark node as dead
                    print(f"[TIMEOUT] Leader Node {self.current_leader} marked as dead")
                    self.mark_dead(self.current_leader)
    
    async def heartbeat_loop(self):
        while True:
            timeout = 5
            await asyncio.sleep(timeout)

            if self.curr_role == NODE_ROLES["LEADER"]:
                await self.send_heartbeats()

    def get_cluster_state(self):
        live_node_count = 0
        for peer,state in self.peers.items():
            if state["is_alive"] is True:
                live_node_count += 1
        print(self.peers)
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
                    print(f"[LOG REPL] Failed to replicate to {peer_id}: {e}")

        if success_count > len(self.peers) // 2:
            print(f"[COMMIT] Majority ack for {entry.command['type']} {entry.command['key']}")

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
                    print(f"[COMMIT REPLICATE] {peer_id} failed: {e}")

    async def fetch_full_log_from_leader(self):
        if not self.current_leader:
            return

        leader_url = self.peers[self.current_leader]["peer_url"]
        async with AsyncClient() as client:
            try:
                resp = await client.get(f"{leader_url}/sync-entries")
                data = resp.json()
                req = AppendEntriesRequest(**data)
                self.handle_append_entries(req)
            except Exception as e:
                print(f"[SYNC] Failed to sync from leader: {e}")