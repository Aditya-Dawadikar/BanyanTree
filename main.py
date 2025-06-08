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
if not NODE_ID:
    raise ValueError("Please set NODE_ID environment variable")

# Load config
PORT, PEERS, NODE_ROLES = load_config(NODE_ID)

# Create RaftNode instance ONCE
node = RaftNode(node_id=NODE_ID)

# Add peers
for peer_id, peer_url in PEERS.items():
    if peer_id != NODE_ID:
        node.add_peer(peer_id, NODE_ROLES["FOLLOWER"], peer_url)

# Add routes with node context
app.include_router(raft_router(node))
app.include_router(store_router(node))

# Background tasks
@app.on_event("startup")
async def start_background_tasks():
    print(f"[STARTUP] Node {NODE_ID} starting background tasks.")
    asyncio.create_task(node.election_timeout_loop())
    asyncio.create_task(node.heartbeat_timeout_loop())
