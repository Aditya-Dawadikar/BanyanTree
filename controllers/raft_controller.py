from raft_node import RaftNode
from models import (
    RequestVoteRequest, RequestVoteResponse,
    AppendEntriesRequest, AppendEntriesResponse,
    HeartBeatRequest, HeartBeatResponse,
    LeaderAnnouncementRequest, LeaderAnnouncementResponse
)

def create_controller(node: RaftNode):
    def request_votes(req: RequestVoteRequest) -> RequestVoteResponse:
        return node.handle_request_vote(req)

    def append_entries(req: AppendEntriesRequest) -> AppendEntriesResponse:
        return node.handle_append_entries(req)

    def handle_heartbeat(req: HeartBeatRequest) -> HeartBeatResponse:
        return node.handle_heartbeat(req)
    
    def handle_leader_announcement(req: LeaderAnnouncementRequest) -> LeaderAnnouncementResponse:
        return node.handle_leader_ack(req)

    return request_votes, append_entries, handle_heartbeat
