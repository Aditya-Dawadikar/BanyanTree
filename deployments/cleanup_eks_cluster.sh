#!/bin/bash

set -e

wait_for_nodegroup_deletion() {
    local ng=$1
    echo "Waiting for nodegroup $ng to be deleted..."
    while eksctl get nodegroup --cluster "$CLUSTER_NAME" --region "$REGION" -o json | jq -e ".[] | select(.Name == \"$ng\")" > /dev/null; do
        sleep 30
        echo "...still deleting nodegroup $ng"
    done
    echo "Nodegroup $ng deleted."
}

wait_for_cluster_deletion() {
    echo "Waiting for EKS cluster to be deleted..."
    while aws eks describe-cluster --region "$REGION" --name "$CLUSTER_NAME" > /dev/null 2>&1; do
        sleep 10
        echo "...still deleting cluster $CLUSTER_NAME"
    done
    echo "Cluster $CLUSTER_NAME deleted."
}


CLUSTER_NAME="banyantree"
REGION="us-east-2"

echo "========================================================="
echo "                  NODEGROUP DELETION"
echo "========================================================="

echo "Fetching nodegroups for cluster: $CLUSTER_NAME..."
NODEGROUPS=$(eksctl get nodegroup --cluster "$CLUSTER_NAME" --region "$REGION" -o json | jq -r '.[].Name')

if [ -n "$NODEGROUPS" ]; then
    echo "Deleting nodegroups..."
    for NG in $NODEGROUPS; do
        echo "- Deleting nodegroup: $NG"
        eksctl delete nodegroup --cluster "$CLUSTER_NAME" --region "$REGION" --name "$NG"
        wait_for_nodegroup_deletion "$NG"
    done
else
    echo "No nodegroups found (already deleted)."
fi

echo "========================================================="
echo "                  EKS CLUSTER DELETION"
echo "========================================================="

echo "Deleting EKS cluster: $CLUSTER_NAME in $REGION..."
eksctl delete cluster --name "$CLUSTER_NAME" --region "$REGION"
wait_for_cluster_deletion

echo "========================================================="
echo "                  CLEAN UP VOLUMES"
echo "========================================================="

echo "Checking for unattached EBS volumes..."
VOLUMES=$(aws ec2 describe-volumes \
  --region "$REGION" \
  --filters Name=status,Values=available \
  --query "Volumes[*].VolumeId" \
  --output text)

if [ -n "$VOLUMES" ]; then
  echo "Found unattached volumes: $VOLUMES"
  for vol in $VOLUMES; do
    aws ec2 delete-volume --region "$REGION" --volume-id "$vol"
    echo "Deleted volume: $vol"
  done
else
  echo "No unattached volumes found."
fi

echo "========================================================="
echo "                  RELEASE UNUSED IPs"
echo "========================================================="

echo "Checking for unused Elastic IPs..."
EIPS=$(aws ec2 describe-addresses \
  --region "$REGION" \
  --query "Addresses[?AssociationId==null].AllocationId" \
  --output text)

if [ -n "$EIPS" ]; then
  echo "Releasing unused Elastic IPs: $EIPS"
  for eip in $EIPS; do
    aws ec2 release-address --region "$REGION" --allocation-id "$eip"
    echo "Released Elastic IP: $eip"
  done
else
  echo "No orphaned Elastic IPs."
fi

echo "========================================================="
echo "                  DELETE ECR REPOSITORY"
echo "========================================================="

REPO_NAME="banyantree"

if aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$REGION" > /dev/null 2>&1; then
  echo "Deleting ECR repository: $REPO_NAME"
  aws ecr delete-repository --repository-name "$REPO_NAME" --region "$REGION" --force
  echo "ECR repository deleted."
else
  echo "ECR repository $REPO_NAME not found (already deleted or never created)."
fi

echo "========================================================="
echo "                  RESIDUAL SERVICE CHECK"
echo "========================================================="

echo "------------- Autoscaling Groups -------------"
aws autoscaling describe-auto-scaling-groups --region $REGION --query 'AutoScalingGroups[*].[AutoScalingGroupName]' --output table

echo "------------- Security Groups -------------"
aws ec2 describe-security-groups --region $REGION --query 'SecurityGroups[?GroupName!=`default`].[GroupId,GroupName]' --output table

echo "------------- ENIs -------------"
aws ec2 describe-network-interfaces --region $REGION --query 'NetworkInterfaces[*].[NetworkInterfaceId,Status,Description]' --output table

echo "------------- Load Balancers -------------"
aws elbv2 describe-load-balancers --region $REGION --query 'LoadBalancers[*].[LoadBalancerName,Type,State.Code]' --output table

echo "------------- CloudFormation Stacks -------------"
aws cloudformation describe-stacks --region $REGION --query 'Stacks[*].[StackName,StackStatus]' --output table

echo "------------- OIDC Providers -------------"
aws iam list-open-id-connect-providers

echo "-------------------------------------------------"
echo "EKS cluster and all detectable cost-associated resources have been reviewed and cleaned."
