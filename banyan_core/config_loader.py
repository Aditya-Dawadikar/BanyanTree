import sys

def load_config(node_id):
    # Full cluster configuration
    all_nodes = {
        "rootkeeper": "http://rootkeeper:8000", # rootkeeper
        "raft-node-0": "http://raft-node-0.raft-node:8000",
        "raft-node-1": "http://raft-node-1.raft-node:8000",
        "raft-node-2": "http://raft-node-2.raft-node:8000",
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

