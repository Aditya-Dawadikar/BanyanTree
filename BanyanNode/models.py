from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class RequestVoteReq(BaseModel):
    term: int
    candidateId: str
    lastLogIndex: int
    lastLogTerm: int

class RequestVoteResp(BaseModel):
    term: int
    voteGranted: bool

class LogEntry(BaseModel):
    term: int
    command: Optional[Dict[str, Any]] = None  # placeholder

class AppendEntriesReq(BaseModel):
    term: int
    leaderId: str
    prevLogIndex: int
    prevLogTerm: int
    entries: List[LogEntry]
    leaderCommit: int

class AppendEntriesResp(BaseModel):
    term: int
    success: bool

class BootstrapConfig(BaseModel):
    node_id: str
    self_url: str
    peers: List[str] = []
    election_timeout_ms_min: int = 1200
    election_timeout_ms_max: int = 2200
    heartbeat_interval_ms: int = 500

class LogEntry(BaseModel):
    term: int
    command: Optional[Dict[str, Any]] = None
