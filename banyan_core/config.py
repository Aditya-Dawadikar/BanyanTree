NODE_ROLES = {
        "ROOTKEEPER": 0,
        "LEADER": 1,
        "FOLLOWER": 2,
        "CANDIDATE": 3,
}

RECORD_STATUS = {
    "UNCOMMITTED": 0,
    "COMMITTED": 1
}

STATUS_MAP = {v: k for k, v in RECORD_STATUS.items()}