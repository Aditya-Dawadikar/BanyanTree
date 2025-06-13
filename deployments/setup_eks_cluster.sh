#!/bin/bash

set -e

echo "========================================================="
echo "                KUBECTL CHECK/INSTALL"
echo "========================================================="

if ! command -v kubectl &> /dev/null; then
  echo "kubectl not found. Installing..."
  curl -LO "https://dl.k8s.io/release/$(curl -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
  chmod +x kubectl
  sudo mv kubectl /usr/local/bin/
  echo "kubectl installed."
else
  echo "kubectl already installed."
fi

echo "========================================================="
echo "                  EKSCTL INSTALLATION"
echo "========================================================="

# Install eksctl
echo "Checking for previous eksctl installation..."
if command -v eksctl &> /dev/null; then
    echo "Removing existing eksctl binary..."
    sudo rm -f "$(command -v eksctl)"
fi

echo "Downloading latest eksctl"
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_Linux_amd64.tar.gz" -o eksctl.tar.gz

echo "Extracting and installing eksctl..."
tar -xzf eksctl.tar.gz
sudo mv eksctl /usr/local/bin/
rm eksctl.tar.gz

echo "eksctl installed"
eksctl version


echo "========================================================="
echo "                  ECR REPO CREATION"
echo "========================================================="

REPO_NAME="banyantree"
REGION="us-east-2"

# Create repo if it doesn't exist
if ! aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$REGION" > /dev/null 2>&1; then
  echo "Creating ECR repository: $REPO_NAME"
  aws ecr create-repository --repository-name "$REPO_NAME" --region "$REGION"
  
  echo "Waiting for ECR repository to become available..."
  while ! aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$REGION" > /dev/null 2>&1; do
    sleep 2
    echo "...still waiting for repository $REPO_NAME"
  done
  echo "ECR repository $REPO_NAME is ready."
else
  echo "ECR repository $REPO_NAME already exists."
fi

echo "========================================================="
echo "                  ECR REPO LIFECYCLE POLICY"
echo "========================================================="


echo "Applying lifecycle policy to expire untagged images older than 6 hours..."
aws ecr put-lifecycle-policy \
  --repository-name "$REPO_NAME" \
  --region "$REGION" \
  --lifecycle-policy-text '{
    "rules": [
      {
        "rulePriority": 1,
        "description": "Expire untagged images older than 1 day",
        "selection": {
          "tagStatus": "untagged",
          "countType": "sinceImagePushed",
          "countUnit": "days",
          "countNumber": 1
        },
        "action": {
          "type": "expire"
        }
      }
    ]
  }'
echo "Lifecycle policy applied."

echo "========================================================="
echo "                  QUERY ECR URI"
echo "========================================================="

REPO_URI=$(aws ecr describe-repositories \
  --repository-names "$REPO_NAME" \
  --region "$REGION" \
  --query "repositories[0].repositoryUri" \
  --output text)

echo "ECR repository URI: $REPO_URI"


echo "========================================================="
echo "                  AUTHENTCIATE DOCKER TO ECR"
echo "========================================================="

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REPO_URI"
echo "Docker authenticated to ECR."


echo "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
echo "ECR repository $REPO_NAME is ready."
echo "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"


echo "========================================================="
echo "                  EKS CLUSTER CREATION"
echo "========================================================="


# Create cluster
CLUSTER_NAME="banyantree"
NODE_TYPE="t3.medium"
MIN_NODES=1
MAX_NODES=4
DESIRED_NODES=3

echo "Creating EKS cluster (this may take 10–15 mins)..."
eksctl create cluster \
  --name "$CLUSTER_NAME" \
  --region "$REGION" \
  --version "1.29" \
  --nodegroup-name "banyantree-ng" \
  --node-type "$NODE_TYPE" \
  --nodes "$DESIRED_NODES" \
  --nodes-min "$MIN_NODES" \
  --nodes-max "$MAX_NODES" \
  --managed \
  --with-oidc \
  --tags "env=dev,project=banyantree"

echo "Cluster creation complete."

# Wait for nodes to be Ready
echo "Waiting for all nodes to become Ready..."
while [[ $(kubectl get nodes --no-headers 2>/dev/null | grep -c " Ready") -lt $MIN_NODES ]]; do
  sleep 10
  echo "...still waiting on nodes to be Ready"
done
echo "All nodes are Ready."

# Wait for all system pods to be Running
echo "Waiting for all system pods to be Running..."
while kubectl get pods -n kube-system --no-headers 2>/dev/null | grep -vE 'Running|Completed' > /dev/null; do
  sleep 10
  echo "...still waiting on system pods"
done
echo "All system pods are Running."

echo "Cluster info:"
aws eks describe-cluster --name "$CLUSTER_NAME" --region "$REGION" --query "cluster.status"

echo "Verifying cluster nodes:"
kubectl get nodes

echo "Verifying system pods:"
kubectl get pods --all-namespaces
