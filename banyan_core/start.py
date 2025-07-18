import sys
import os
import subprocess
from config import NODE_ROLES

if len(sys.argv) < 3:
    print("Usage: python start.py <node_id> <port>")
    sys.exit(1)

node_id = sys.argv[1]
port = sys.argv[2]
role = "ROOTKEEPER" if node_id == "node0" else "FOLLOWER"

subprocess.run([
    "uvicorn", "main:app",
    "--port", port, "--reload"
], env={**os.environ, "NODE_ID": node_id, "NODE_PORT": port, "NODE_ROLE": role})
