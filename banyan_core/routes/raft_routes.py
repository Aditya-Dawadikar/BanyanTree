from fastapi import APIRouter
from raft_node import RaftNode
from controllers.raft_controller import create_controller
from models import *
from fastapi.responses import RedirectResponse, JSONResponse
from config import NODE_ROLES

def get_router_with_node(node: RaftNode):
    router = APIRouter()
    request_votes, append_entries = create_controller(node)

    @router.post("/ping", response_model=HeartBeatResponse)
    async def receive_heartbeat(req: HeartBeatRequest):
        print(f"[PING] Received from {req.node_id}")
        return await node.handle_heartbeat(req)

    @router.post("/request-vote", response_model=RequestVoteResponse)
    async def vote_endpoint(req: RequestVoteRequest):
        return await request_votes(req)

    @router.post("/append-entries", response_model=AppendEntriesResponse)
    async def append_endpoint(req: AppendEntriesRequest):
        return await append_entries(req)
    
    @router.get("/sync-entries", response_model=AppendEntriesRequest)
    async def sync_entries():
        print(f"received sync entries msg")

        if node.curr_role != NODE_ROLES["LEADER"]:
            if not node.current_leader or node.current_leader not in node.peers:
                return JSONResponse(status_code=503, content={"error": "No known leader to sync from."})
            
            return RedirectResponse(url=f"{node.peers[node.current_leader]['peer_url']}/sync-entries")


        return AppendEntriesRequest(
            term=node.current_term,
            leader_id=node.node_id,
            prev_log_index=-1,
            prev_log_term=0,
            entries=node.log,
            leader_commit=node.commit_index
        )
    
    @router.get("/cluster-state")
    async def cluster_state():
        return await node.get_cluster_state()

    @router.post("/leader-announcement", response_model = LeaderAnnouncementResponse)
    async def leader_announcement_ack(req: LeaderAnnouncementRequest):
        return await node.handle_leader_ack(req)

    @router.get("/leader-consensus", response_model = LeaderConsensusResponse)
    async def get_leader_consesnsus():
        return await node.get_leader()

    return router
