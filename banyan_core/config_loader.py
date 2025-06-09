import sys

def load_config(node_id):
    # Full cluster configuration
    all_nodes = {
        "node1": "http://localhost:8001",
        "node2": "http://localhost:8002",
        "node3": "http://localhost:8003",
    }

    if node_id not in all_nodes:
        raise Exception(f"Unknown node_id: {node_id}")

    # Get port from current node's URL
    port = int(all_nodes[node_id].split(":")[-1])

    # Remove current node from peer list
    peers = {nid: url for nid, url in all_nodes.items() if nid != node_id}

    # Define node roles
    NODE_ROLES = {
        "LEADER": 0,
        "FOLLOWER": 1,
        "CANDIDATE": 2
    }

    return port, peers, NODE_ROLES

