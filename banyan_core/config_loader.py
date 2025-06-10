import sys

def load_config(node_id):
    # Full cluster configuration
    all_nodes = {
        "node0": "http://localhost:8000", # RootKeeper
        "node1": "http://localhost:8001",
        "node2": "http://localhost:8002",
        "node3": "http://localhost:8003",
    }

    if node_id not in all_nodes:
        raise Exception(f"Unknown node_id: {node_id}")

    # Remove current node from peer list
    peers = {nid: url for nid, url in all_nodes.items() if nid != node_id}

    # Define node roles
    NODE_ROLES = {
        "ROOTKEEPER": 0,
        "LEADER": 1,
        "FOLLOWER": 2,
        "CANDIDATE": 3,
    }

    return peers, NODE_ROLES

