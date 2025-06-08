import sys
import os
import subprocess

if len(sys.argv) < 3:
    print("Usage: python start.py <node_id> <port>")
    sys.exit(1)

node_id = sys.argv[1]
port = sys.argv[2]

subprocess.run([
    "uvicorn", "main:app",
    "--port", port, "--reload"
], env={**os.environ, "NODE_ID": node_id})
