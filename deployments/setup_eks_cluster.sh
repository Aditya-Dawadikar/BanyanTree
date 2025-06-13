#!/bin/bash

set -euo pipefail

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


echo "Applying lifecycle policy to expire untagged images older than 1 day..."
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


echo "Waiting for nodes to be ready..."
while [[ $(kubectl get nodes --no-headers 2>/dev/null | grep -c " Ready") -lt $MIN_NODES ]]; do
  sleep 10
  echo "...still waiting on nodes"
done

echo "========================================================="
echo "          SETUP IAM ROLE FOR EBS CSI DRIVER"
echo "========================================================="

ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
OIDC_ID=$(aws eks describe-cluster --name "$CLUSTER_NAME" --region "$REGION" --query "cluster.identity.oidc.issuer" --output text | cut -d '/' -f5)

cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::$ACCOUNT_ID:oidc-provider/oidc.eks.$REGION.amazonaws.com/id/$OIDC_ID"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.$REGION.amazonaws.com/id/$OIDC_ID:sub": "system:serviceaccount:kube-system:ebs-csi-controller-sa"
        }
      }
    }
  ]
}
EOF

ROLE_NAME="AmazonEKS_EBS_CSI_DriverRole"


if ! aws iam get-role --role-name "$ROLE_NAME" &>/dev/null; then
  echo "Creating IAM role: $ROLE_NAME"
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document file://trust-policy.json
else
  echo "IAM role $ROLE_NAME already exists."
fi


aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy

echo "========================================================="
echo "      INSTALL EBS CSI DRIVER ADDON ON THE CLUSTER"
echo "========================================================="

aws eks create-addon \
  --cluster-name "$CLUSTER_NAME" \
  --region "$REGION" \
  --addon-name aws-ebs-csi-driver \
  --service-account-role-arn arn:aws:iam::$ACCOUNT_ID:role/$ROLE_NAME \
  --resolve-conflicts OVERWRITE || echo "Addon may already exist."

echo "Waiting for EBS CSI driver pods..."
while kubectl get pods -n kube-system | grep ebs-csi | grep -vE 'Running|Completed' > /dev/null; do
  sleep 10
  echo "...waiting on EBS CSI driver to be ready"
done

echo "✅ Cluster ready for StatefulSet PVCs"

rm -f trust-policy.json

echo "Cluster info:"
aws eks describe-cluster --name "$CLUSTER_NAME" --region "$REGION" --query "cluster.status"
kubectl get nodes
kubectl get pods -n kube-system
