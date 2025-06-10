import os
import asyncio
from fastapi import FastAPI
from routes.raft_routes import get_router_with_node as raft_router
from routes.store_routes import get_store_router as store_router
from config_loader import load_config
from raft_node import RaftNode

app = FastAPI()

# Get node ID from environment variable
NODE_ID = os.getenv("NODE_ID")
NODE_PORT = os.getenv("NODE_PORT")
ROLE = os.getenv("NODE_ROLE")

if not NODE_ID:
    raise ValueError("Please set NODE_ID environment variable")

# Load config
PEERS, NODE_ROLES = load_config(NODE_ID)

# Create RaftNode instance
node = RaftNode(node_id=NODE_ID)

# Identify rootkeeper ID (assume node0 is rootkeeper)
ROOTKEEPER_ID = "node0"
node.rootkeeper = ROOTKEEPER_ID  # store rootkeeper's ID

# Set role from env
ROLE = os.getenv("NODE_ROLE")
if ROLE is None:
    raise ValueError("NODE_ROLE env var not set")

# If this node is RootKeeper, assign role and skip adding self as peer
if NODE_ID == ROOTKEEPER_ID:
    print("[SELF] Marking myself as RootKeeper")
    node.curr_role = NODE_ROLES["ROOTKEEPER"]
else:
    node.curr_role = NODE_ROLES["FOLLOWER"]

# Add all peers, including the RootKeeper
for peer_id, peer_url in PEERS.items():
    if peer_id == NODE_ID:
        continue  # Don't add self

    # If the peer is rootkeeper, add with ROOTKEEPER role
    role = NODE_ROLES["ROOTKEEPER"] if peer_id == ROOTKEEPER_ID else NODE_ROLES["FOLLOWER"]
    node.add_peer(peer_id, role, peer_url)

# Add routes with node context
app.include_router(raft_router(node))
app.include_router(store_router(node))

# Background tasks
@app.on_event("startup")
async def start_background_tasks():
    print(f"[STARTUP] Node {NODE_ID} starting background tasks.")
    if node.curr_role == NODE_ROLES["ROOTKEEPER"]:
        asyncio.create_task(node.heartbeat_timeout_loop())
        node.heartbeat_task = asyncio.create_task(node.rootkeeper_loop())
    else:
        asyncio.create_task(node.election_timeout_loop())
        asyncio.create_task(node.heartbeat_timeout_loop())
        asyncio.create_task(node.fetch_full_log_from_leader())
    
    asyncio.create_task(node.consensus_monitor_loop())
