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

delete_cloudformation_stacks() {
    echo "Cleaning up CloudFormation stacks..."
    STACKS=$(aws cloudformation describe-stacks --region "$REGION" --query "Stacks[*].StackName" --output text)
    for stack in $STACKS; do
        if [[ "$stack" == eksctl-* ]]; then
            echo "- Deleting stack: $stack"
            aws cloudformation delete-stack --region "$REGION" --stack-name "$stack"
        fi
    done

    for stack in $STACKS; do
        if [[ "$stack" == eksctl-* ]]; then
            while aws cloudformation describe-stacks --region "$REGION" --stack-name "$stack" > /dev/null 2>&1; do
                sleep 10
                echo "...waiting for stack $stack to delete"
            done
            echo "Deleted stack: $stack"
        fi
    done
}

delete_oidc_providers() {
    echo "Cleaning up OIDC providers..."
    OIDC_PROVIDERS=$(aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[].Arn" --output text)
    for oidc in $OIDC_PROVIDERS; do
        echo "- Deleting OIDC provider: $oidc"
        aws iam delete-open-id-connect-provider --open-id-connect-provider-arn "$oidc"
    done
}

delete_orphaned_security_groups() {
    echo "Cleaning up orphaned security groups..."
    SGS=$(aws ec2 describe-security-groups --region "$REGION" --query 'SecurityGroups[?GroupName!=`default`].[GroupId]' --output text)
    for sg in $SGS; do
        if aws ec2 delete-security-group --region "$REGION" --group-id "$sg" 2>/dev/null; then
            echo "- Deleted security group: $sg"
        else
            echo "- Skipped in-use security group: $sg"
        fi
    done
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
if ! eksctl delete cluster --name "$CLUSTER_NAME" --region "$REGION"; then
    echo "Cluster not found or already deleted. Skipping cluster deletion."
fi
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

echo "------------- CloudFormation Stacks -------------"
echo "Checking for residual CloudFormation stacks..."
STACK_COUNT=$(aws cloudformation describe-stacks --region "$REGION" --query 'length(Stacks[?starts_with(StackName, `eksctl-`)])')
if [ "$STACK_COUNT" -gt 0 ]; then
    delete_cloudformation_stacks
else
    echo "No EKS-related CloudFormation stacks found."
fi

echo "------------- OIDC Providers -------------"
echo "Checking for OIDC providers..."
OIDC_COUNT=$(aws iam list-open-id-connect-providers --query 'length(OpenIDConnectProviderList)')
if [ "$OIDC_COUNT" -gt 0 ]; then
    delete_oidc_providers
else
    echo "No OIDC providers found."
fi

echo "------------- Security Groups -------------"
echo "Checking for orphaned Security Groups..."
SG_COUNT=$(aws ec2 describe-security-groups --region "$REGION" --query 'length(SecurityGroups[?GroupName!=`default`])')
if [ "$SG_COUNT" -gt 0 ]; then
    delete_orphaned_security_groups
else
    echo "No non-default security groups found."
fi

echo "------------- Autoscaling Groups -------------"
aws autoscaling describe-auto-scaling-groups --region $REGION --query 'AutoScalingGroups[*].[AutoScalingGroupName]' --output table

echo "------------- ENIs -------------"
aws ec2 describe-network-interfaces --region $REGION --query 'NetworkInterfaces[*].[NetworkInterfaceId,Status,Description]' --output table

echo "------------- Load Balancers -------------"
aws elbv2 describe-load-balancers --region $REGION --query 'LoadBalancers[*].[LoadBalancerName,Type,State.Code]' --output table

echo "-------------------------------------------------"
echo "EKS cluster and all detectable cost-associated resources have been reviewed and cleaned."
