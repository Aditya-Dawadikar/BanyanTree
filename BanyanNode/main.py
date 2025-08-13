import os
from fastapi import FastAPI
import random
import time
import requests


app = FastAPI()

NODE_ID = os.getenv("NODE_ID", "node-1")
SELF_URL = os.getenv("SELF_URL", "http://localhost:8001")
ROOTKEEPER_URL = os.getenv("ROOTKEEPER_URL", "http://localhost:8000")  # where /cluster lives
ELECTION_TIMEOUT_MS_RANGE = (1200, 2200)  # randomized
HEARTBEAT_INTERVAL_MS = 500

@app.get("/health")
def health():
    return {
        "status": True
    }
