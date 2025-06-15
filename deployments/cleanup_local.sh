#!/bin/bash

set -e

# Get the absolute path of the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENTS_DIR="$SCRIPT_DIR/k8s"

echo ">> Cleaning up old Kubernetes resources..."
kubectl delete job --all || true
kubectl delete deployment --all || true
kubectl delete statefulset --all || true
kubectl delete configmap --all || true
kubectl delete pvc --all || true

echo "✅ All components deleted successfully"
