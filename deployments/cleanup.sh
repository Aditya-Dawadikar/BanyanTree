#!/bin/bash

set -e
PROJECT_DIR="$HOME/BanyanTree"
ECR_REPO="777064612419.dkr.ecr.us-east-2.amazonaws.com/banyantree"
AWS_REGION="us-east-2"

current_dir=$(pwd)
echo "Current Dir: $current_dir"
echo "PROJECT_DIR: $PROJECT_DIR"


echo ">> Cleaning up Kubernetes resources..."
kubectl delete job create-kafka-topics --ignore-not-found
kubectl delete deployment kafka rootkeeper sap-streamer elasticsearch zookeeper --ignore-not-found
kubectl delete statefulset raft-node --ignore-not-found
kubectl delete configmap kafka-init-scripts --ignore-not-found
kubectl delete pvc --selector app=raft-node --ignore-not-found


echo "✅ All components cleaned successfully."
