from fastapi import APIRouter
from raft_node import RaftNode
from controllers.raft_controller import create_controller
from models import *
from fastapi.responses import JSONResponse

def get_router_with_node(node: RaftNode):
    router = APIRouter()
    # node = RaftNode(node_id=node_id)
    request_votes, append_entries, handle_heartbeat = create_controller(node)

    @router.post("/ping", response_model=HeartBeatResponse)
    async def receive_heartbeat(req: HeartBeatRequest):
        # return handle_heartbeat(req)
        # response = node.handle_heartbeat(req)
        # return JSONResponse(content=response.dict())
        print(f"[PING] Received from {req.node_id}")
        return node.handle_heartbeat(req)

    @router.post("/request-vote", response_model=RequestVoteResponse)
    async def vote_endpoint(req: RequestVoteRequest):
        return request_votes(req)

    @router.post("/append-entries", response_model=AppendEntriesResponse)
    async def append_endpoint(req: AppendEntriesRequest):
        return append_entries(req)
    
    @router.get("/cluster-state")
    async def cluster_state():
        return node.get_cluster_state()


    @router.post("/leader-announcement", response_model = LeaderAnnouncementResponse)
    async def leader_announcement_ack(req: LeaderAnnouncementRequest):
        return node.handle_leader_ack(req)

    return router
