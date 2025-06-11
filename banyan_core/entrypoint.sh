#!/bin/bash

# Fallbacks if env vars are not provided
: "${NODE_ID:=node1}"
: "${NODE_PORT:=8000}"

exec python start.py "$NODE_ID" "$NODE_PORT"
