NODE_ROLES = {
    "LEADER": 0,
    "FOLLOWER": 1,
    "CANDIDATE": 2
}

RECORD_STATUS = {
    "UNCOMMITTED": 0,
    "COMMITTED": 1
}

STATUS_MAP = {v: k for k, v in RECORD_STATUS.items()}