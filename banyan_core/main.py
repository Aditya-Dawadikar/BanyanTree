import os
import asyncio
from fastapi import FastAPI
from routes.raft_routes import get_router_with_node as raft_router
from routes.store_routes import get_store_router as store_router
from config_loader import load_config
from raft_node import RaftNode
from logger import BanyanCoreLogger


app = FastAPI()


# Get node ID from environment variable
NODE_ID = os.getenv("NODE_ID")
NODE_PORT = os.getenv("NODE_PORT")
ROLE = os.getenv("NODE_ROLE")

if not NODE_ID:
    raise ValueError("Please set NODE_ID environment variable")
    
# Identify rootkeeper ID (assume node0 is rootkeeper)
ROOTKEEPER_ID = "node0"

# Load config
PEERS, NODE_ROLES = load_config(NODE_ID)


async def initialize_node() -> RaftNode:


    # Create RaftNode instance
    logger = BanyanCoreLogger(node_id=NODE_ID)
    await logger.start_producer()

    node = RaftNode(node_id=NODE_ID,
                logger=logger)
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
        await node.add_peer(peer_id, role, peer_url)
    
    return node

# Initialize node at startup
@app.on_event("startup")
async def startup_event():
    try:
        node = await initialize_node()
        app.state.node = node  # Store node in app state for access in routes
        
        # Add routes with node context
        app.include_router(raft_router(node))
        app.include_router(store_router(node))

        # Start background tasks based on role
        print(f"[STARTUP] Node {node.node_id} starting background tasks.")
        asyncio.create_task(node.consensus_monitor_loop())
        
        if node.curr_role == NODE_ROLES["ROOTKEEPER"]:
            asyncio.create_task(node.heartbeat_timeout_loop())
            node.heartbeat_task = asyncio.create_task(node.rootkeeper_loop())
        else:
            asyncio.create_task(node.election_timeout_loop())
            asyncio.create_task(node.heartbeat_timeout_loop())
            asyncio.create_task(node.fetch_full_log_from_leader())
            
    except Exception as e:
        print(f"Failed to initialize node: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown"""
    node = app.state.node
    if hasattr(node, 'logger'):
        await node.logger.stop_producer()
    
    # Cancel all running tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
