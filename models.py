from pydantic import BaseModel
from typing import List, Optional

class HeartBeatRequest(BaseModel):
    node_id: str
    timestamp: str

class HeartBeatResponse(BaseModel):
    ack: bool
    timestamp: str

class LogEntry(BaseModel):
    term: int
    command: str

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