from raft_node import RaftNode
from models import (
    RequestVoteRequest, RequestVoteResponse,
    AppendEntriesRequest, AppendEntriesResponse
)

def create_controller(node: RaftNode):
    def request_votes(req: RequestVoteRequest) -> RequestVoteResponse:
        return node.handle_request_vote(req)

    def append_entries(req: AppendEntriesRequest) -> AppendEntriesResponse:
        return node.handle_append_entries(req)

    return request_votes, append_entries
