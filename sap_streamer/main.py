import os
import asyncio
from fastapi import FastAPI
from routes import get_cluster_router
from consumer import consume_logs
from elasticsearch import Elasticsearch
import logging
import sys

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Clear existing handlers if any
if logger.hasHandlers():
    logger.handlers.clear()

# Create handler that logs to stdout
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('[%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Keep reference to background task
task_handle = None

print("[BOOT] App module loaded")
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    global task_handle
    try:
        # Environment vars
        ES_SERVER = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")
        KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

        # Create client
        es = Elasticsearch(ES_SERVER,
                           verify_certs=False,   # or provide certs if available
                            ssl_show_warn=False)

        # Retry until Elasticsearch is up
        for attempt in range(20):
            if es.ping():
                print(f"[INFO] Elasticsearch is reachable after {attempt+1} tries.")
                break
            print(f"[WAITING] Elasticsearch not ready yet, retrying... ({attempt+1}/20)")
            await asyncio.sleep(3)
        else:
            raise ConnectionError("Elasticsearch did not become ready in time.")

        app.state.es = es
        print("[STARTUP] Connecting to Kafka...")
        task_handle = asyncio.create_task(consume_logs(es))
        print("[STARTUP] Log consumer task started")

        app.include_router(get_cluster_router(app.state.es), prefix="/cluster")

    except Exception as e:
        print(f"[ERROR] Failed to start log consumer: {e}", flush=True)
        raise

@app.on_event("shutdown")
async def shutdown_event():
    global task_handle
    print("[SHUTDOWN] Cancelling background tasks...", flush=True)
    if task_handle:
        task_handle.cancel()
        try:
            await task_handle
        except asyncio.CancelledError:
            print("[SHUTDOWN] Consumer task cancelled cleanly", flush=True)
    print("[SHUTDOWN] Cleanup complete", flush=True)
