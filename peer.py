from config import NODE_ROLES

class Peer:
    def __init__(self, node_id: str,  last_seen: str, is_alive: bool = False, role: int = NODE_ROLES["FOLLOWER"]):
        self.node_id = node_id
        self.is_alive = is_alive
        self.last_seen = str
        self.role = role
