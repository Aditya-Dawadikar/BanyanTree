from pydantic import BaseModel
from typing import List, Optional, Dict, Union

class HeartBeatRequest(BaseModel):
    node_id: str
    timestamp: str

class HeartBeatResponse(BaseModel):
    ack: bool
    timestamp: str

class LogEntry(BaseModel):
    term: int
    command: Dict[str, Union[str, int, float, bool]]
    index: int
    committed: bool = False

class RequestVoteRequest(BaseModel):
    term: int
    candidate_id: str
    last_log_index: int
    last_log_term: int

class RequestVoteResponse(BaseModel):
    term: int
    vote_granted: bool

class LeaderAnnouncementRequest(BaseModel):
    term: int
    leader_id: str

class LeaderAnnouncementResponse(BaseModel):
    ack: bool
    timestamp: str

class AppendEntriesRequest(BaseModel):
    term: int
    leader_id: str
    prev_log_index: int
    prev_log_term: int
    entries: List[LogEntry] = []
    leader_commit: int

class AppendEntriesResponse(BaseModel):
    term: int
    success: bool

class AddRecordRequest(BaseModel):
    key: str
    value: str

class AddRecordResponse(BaseModel):
    success: bool
    message: str
    key: str

class GetRecordResponse(BaseModel):
    key: str
    value: Optional[str]  # or Any if needed
    status: str
    is_deleted: bool
    created_at: float
    last_updated_at: float
    last_committed_at: Optional[float]

class LeaderConsensusResponse(BaseModel):
    leader_id: Optional[str]
    reported_by: str
    reported_at: float
