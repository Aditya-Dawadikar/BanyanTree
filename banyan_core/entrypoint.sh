#!/bin/bash

# Get pod name from environment if not set
: "${NODE_ID:=$(hostname)}"
: "${NODE_PORT:=8000}"

exec python start.py "$NODE_ID" "$NODE_PORT"
