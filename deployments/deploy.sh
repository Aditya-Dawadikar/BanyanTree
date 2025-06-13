#!/bin/bash

set -e
PROJECT_DIR="$HOME/BanyanTree"
ECR_REPO="777064612419.dkr.ecr.us-east-2.amazonaws.com/banyantree"
AWS_REGION="us-east-2"

current_dir=$(pwd)
echo "Current Dir: $current_dir"
echo "PROJECT_DIR: $PROJECT_DIR"


echo ">> Pulling latest code..."
cd "$PROJECT_DIR"
git pull origin master

echo ">> Building and pushing Docker images..."
docker build -t $ECR_REPO:raft-node -f banyan_core/Dockerfile banyan_core
docker push $ECR_REPO:raft-node

docker tag $ECR_REPO:raft-node $ECR_REPO:rootkeeper
docker push $ECR_REPO:rootkeeper

docker build -t $ECR_REPO:sap-streamer -f sap_streamer/Dockerfile sap_streamer
docker push $ECR_REPO:sap-streamer

echo ">> Cleaning up old Kubernetes resources..."
kubectl delete job create-kafka-topics --ignore-not-found
kubectl delete deployment kafka rootkeeper sap-streamer elasticsearch zookeeper --ignore-not-found
kubectl delete statefulset raft-node --ignore-not-found
kubectl delete configmap kafka-init-scripts --ignore-not-found
kubectl delete pvc --selector app=raft-node --ignore-not-found

echo ">> Deploying ConfigMaps..."
kubectl apply -f deployments/k8s/kafka-init-configmap.yaml

echo ">> Deploying Zookeeper..."
kubectl apply -f deployments/k8s/zookeeper-deployment.yaml

echo ">> Deploying Kafka..."
kubectl apply -f deployments/k8s/kafka-deployment.yaml

echo ">> Deploying Kafka topic creation job..."
kubectl apply -f deployments/k8s/kafka-create-topics-job.yaml

echo ">> Deploying Elasticsearch..."
kubectl apply -f deployments/k8s/elasticsearch-deployment.yaml

echo ">> Deploying Raft nodes..."
kubectl apply -f deployments/k8s/raft-node-statefulset.yaml

echo ">> Deploying Rootkeeper and SapStreamer..."
kubectl apply -f deployments/k8s/rootkeeper-deployment.yaml
kubectl apply -f deployments/k8s/sap-streamer-deployment.yaml

echo "✅ All components deployed successfully."
