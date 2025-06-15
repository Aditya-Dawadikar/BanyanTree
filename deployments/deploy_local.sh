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

echo ">> Deploying Zookeeper..."
kubectl apply -f "$DEPLOYMENTS_DIR/zookeeper-deployment.yaml"
kubectl apply -f "$DEPLOYMENTS_DIR/zookeeper-service.yaml"

echo ">> Waiting for Zookeeper to be ready..."
kubectl wait --for=condition=Ready pod -l app=zookeeper --timeout=120s

echo ">> Deploying Kafka..."
kubectl apply -f "$DEPLOYMENTS_DIR/kafka-deployment.yaml"
kubectl apply -f "$DEPLOYMENTS_DIR/kafka-service.yaml"
kubectl apply -f "$DEPLOYMENTS_DIR/kafka-nodeport.yaml"

echo ">> Waiting for Kafka to be ready..."
kubectl wait --for=condition=Ready pod -l app=kafka --timeout=120s

echo ">> Creating Kafka topics..."
KAFKA_POD=$(kubectl get pods -l app=kafka -o jsonpath='{.items[0].metadata.name}')
kubectl exec $KAFKA_POD -- \
  kafka-topics.sh --create \
  --bootstrap-server localhost:9092 \
  --topic raft-logs \
  --partitions 1 \
  --replication-factor 1

kubectl exec $KAFKA_POD -- \
  kafka-topics.sh --create \
  --bootstrap-server localhost:9092 \
  --topic store-logs \
  --partitions 1 \
  --replication-factor 1

echo ">> Verifying topics were created..."
kubectl exec $KAFKA_POD -- \
  kafka-topics.sh --list \
  --bootstrap-server localhost:9092

echo ">> Deploying ElasticSearch..."
kubectl apply -f "$DEPLOYMENTS_DIR/es-deployment.yaml"
kubectl apply -f "$DEPLOYMENTS_DIR/es-service.yaml"

echo ">> Deploying Raftnodes..."
kubectl apply -f "$DEPLOYMENTS_DIR/raft-node-service.yaml"
kubectl apply -f "$DEPLOYMENTS_DIR/raft-node-statefulset.yaml"

echo ">> Deploying Rootkeeper..."
kubectl apply -f "$DEPLOYMENTS_DIR/rootkeeper-service.yaml"
kubectl apply -f "$DEPLOYMENTS_DIR/rootkeeper-deployment.yaml"

echo ">> Deploying SapStreamer..."
kubectl apply -f "$DEPLOYMENTS_DIR/sap-streamer-service.yaml"
kubectl apply -f "$DEPLOYMENTS_DIR/sap-streamer-deployment.yaml"

echo ">> Deploying CURL Tester..."
kubectl apply -f "$DEPLOYMENTS_DIR/curl-tester.yaml"

echo "✅ All components deployed and topics created successfully."
