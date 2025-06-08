import asyncio
from config import NODE_ROLES
from httpx import AsyncClient
from datetime import datetime, timezone
from peer import Peer
from models import (RequestVoteRequest,
                    RequestVoteResponse,
                    AppendEntriesRequest,
                    AppendEntriesResponse,
                    HeartBeatRequest,
                    HeartBeatResponse,
                    LeaderAnnouncementRequest,
                    LeaderAnnouncementResponse)
import random



class RaftNode:
    def __init__(self, node_id:str):
        self.node_id = node_id
        self.curr_role = NODE_ROLES["FOLLOWER"]
    
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
        print("&&&&&&&&&&&&&&&&&&&&&")
        print(req.term, self.current_term)
        self.is_election = True
        if req.term < self.current_term:
            return RequestVoteResponse(vote_granted=False, term=self.current_term)

        # Step 2: If candidates term is greater than my current term,
        # update my term and become follower
        self.current_term = req.term
        return self.become_follower(req.term, req.candidate_id)

    def handle_append_entries(self, req: AppendEntriesRequest):
        return AppendEntriesResponse(term=self.current_term, success=False)

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

        
        print("***************************")
        print(self.current_term)
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

        if req.leader_id not in self.peers:
            return LeaderAnnouncementResponse(
                    ack = False,
                    timestamp= str(datetime.now(timezone.utc).timestamp())
                )

        if self.peers[req.leader_id]["role"] == NODE_ROLES["CANDIDATE"]:
            # mark as leader
            self.peers[req.leader_id]["role"] = NODE_ROLES["LEADER"]
            self.current_leader = req.leader_id
            self.voted_for = None
            self.is_election = False
            return LeaderAnnouncementResponse(
                ack = True,
                timestamp = str(datetime.now(timezone.utc).timestamp())
            )

        return LeaderAnnouncementResponse(
                    ack = False,
                    timestamp= str(datetime.now(timezone.utc).timestamp())
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

                except Exception as e:
                    print(f"[HEARTBEAT] Failed to reach {peer}: {e}")

    def handle_heartbeat(self, req: HeartBeatRequest):
        timestamp = str(datetime.now(timezone.utc).timestamp())
        if req.node_id in self.peers:
            self.peers[req.node_id]["is_alive"] = True
            self.peers[req.node_id]["last_seen"] = timestamp
        return HeartBeatResponse(ack=True, timestamp=timestamp)
    
    def mark_dead(self, node_id):
        try:
            if node_id not in self.peers:
                raise Exception("Node not found")
            self.peers[node_id]["is_alive"] = False
            self.peers[node_id]["role"] = None
            if self.current_leader == node_id:
                # leader dead
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

            if self.curr_role != NODE_ROLES["LEADER"] and \
                (self.current_leader is None or 
                 (self.current_leader != self.node_id and 
                  self.peers[self.current_leader]["is_alive"] is False)):
                

                live_peer_count = 0
                for peer,state in self.peers.items():
                    if state["is_alive"] is True:
                        live_peer_count += 1
                
                if live_peer_count > len(self.peers)//2 and self.is_election is False:
                    print(f"[TIMEOUT] Node {self.node_id} starting election for term {self.current_term + 1}")
                    await self.become_candidate()
                else:
                    print(f"[TIMEOUT] Waiting for majority nodes to join cluster")
    
    async def heartbeat_timeout_loop(self):
        while True:
            timeout = 5
            await asyncio.sleep(timeout)

            curr_timestamp = datetime.now(timezone.utc).timestamp()

            for peer, val in self.peers.items():
                last_seen = float(val["last_seen"])

                delta_secs = curr_timestamp - last_seen
                print(peer, delta_secs)
                if delta_secs > self.max_wait:
                    # mark node as dead
                    print(f"[TIMEOUT] Node {peer} marked as dead")
                    self.mark_dead(peer)
    
    async def heartbeat_loop(self):
        while True:
            timeout = 5
            await asyncio.sleep(timeout)

            await self.send_heartbeats()

    def get_cluster_state(self):
        live_node_count = 0
        for peer,state in self.peers.items():
            if state["is_alive"] is True:
                live_node_count += 1
        print(self.peers)
        return {
            "node_id": self.node_id,
            "role": self.curr_role,
            "current_term": self.current_term,
            "leader": self.current_leader,
            "is_election": self.is_election,
            "live_node_count": live_node_count,
            "total_nodes": len(self.peers),
            "peers": self.peers
        }
