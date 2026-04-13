#!/usr/bin/env bash
#
# End-to-end ALPHA lab bootstrap for a blank AWS account.
# - Deploys ALPHA infra via CDK (Step Functions, Lambdas, Dynamo tables)
# - Creates an over-privileged demo IAM role
# - Ensures IAM Access Analyzer + CloudTrail are present
# - Runs `alpha analyze` to generate a proposal you can demo
#
# Usage:
#   ./scripts/alpha_lab.sh apply   # deploy & generate proposal
#   ./scripts/alpha_lab.sh cleanup # destroy stack and demo role
#
set -euo pipefail

ACTION="${1:-apply}"
REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)"
STACK_NAME="AlphaStack"
DEMO_ROLE_NAME="AlphaDemoOverPerm"
TRAIL_NAME="alpha-lab-trail"
ANALYZER_NAME="alpha-lab-analyzer"
PROFILE_NAME="AlphaDemoProfile"
OUTPUTS_FILE="$(pwd)/.alpha_lab_outputs.json"

log() { echo "[$(date +%H:%M:%S)] $*"; }

require_bin() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required binary: $1" >&2
    exit 1
  fi
}

ensure_prereqs() {
  require_bin aws
  require_bin node
  require_bin npm
  require_bin cdk
  require_bin uv
}

ensure_access_analyzer() {
  log "Ensuring IAM Access Analyzer '${ANALYZER_NAME}' exists..."
  EXISTING=$(aws accessanalyzer list-analyzers --region "$REGION" \
    --query "analyzers[?name=='${ANALYZER_NAME}'].name" --output text 2>/dev/null || true)
  if [[ -z "$EXISTING" ]]; then
    aws accessanalyzer create-analyzer --type ACCOUNT --name "$ANALYZER_NAME" --region "$REGION"
    log "Created Access Analyzer '${ANALYZER_NAME}'"
  else
    log "Access Analyzer '${ANALYZER_NAME}' already exists"
  fi
}

ensure_cloudtrail() {
  log "Ensuring CloudTrail trail '${TRAIL_NAME}' exists..."
  if ! aws cloudtrail describe-trails --region "$REGION" --query "trailList[?Name=='${TRAIL_NAME}']" --output text >/dev/null 2>&1; then
    BUCKET="alpha-lab-trail-${ACCOUNT_ID:-demo}-$(date +%s)"
    aws s3 mb "s3://${BUCKET}" >/dev/null
    aws cloudtrail create-trail --name "$TRAIL_NAME" --s3-bucket-name "$BUCKET" --region "$REGION"
    aws cloudtrail start-logging --name "$TRAIL_NAME" --region "$REGION"
  fi
}

create_demo_role() {
  log "Creating over-privileged demo role ${DEMO_ROLE_NAME}..."
  if aws iam get-role --role-name "$DEMO_ROLE_NAME" >/dev/null 2>&1; then
    log "Role already exists, skipping create"
    return
  fi
  aws iam create-role \
    --role-name "$DEMO_ROLE_NAME" \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{"Effect": "Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]
    }'
  aws iam put-role-policy \
    --role-name "$DEMO_ROLE_NAME" \
    --policy-name "OverPermAdminLike" \
    --policy-document '{
      "Version": "2012-10-17",
      "Statement": [
        {"Effect": "Allow", "Action": "s3:*", "Resource": "*"},
        {"Effect": "Allow", "Action": "dynamodb:*", "Resource": "*"},
        {"Effect": "Allow", "Action": "logs:*", "Resource": "*"}
      ]
    }'
}

generate_role_usage() {
  log "Generating CloudTrail activity for ${DEMO_ROLE_NAME} (short EC2 session)..."
  # Create instance profile and attach role
  if ! aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null 2>&1; then
    aws iam create-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null
    aws iam add-role-to-instance-profile --instance-profile-name "$PROFILE_NAME" --role-name "$DEMO_ROLE_NAME" >/dev/null
  fi

  AMI_ID=$(aws ssm get-parameters --names /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 --query 'Parameters[0].Value' --output text --region "$REGION")
  INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type t4g.nano \
    --iam-instance-profile Name="$PROFILE_NAME" \
    --user-data '#!/bin/bash
      aws s3 ls >/tmp/s3.txt
      aws dynamodb list-tables >/tmp/ddb.txt
      aws logs describe-log-groups >/tmp/logs.txt
      sleep 60' \
    --query 'Instances[0].InstanceId' \
    --output text \
    --region "$REGION")

  log "Instance $INSTANCE_ID launched to create telemetry; waiting 90s..."
  sleep 90
  aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --region "$REGION" >/dev/null
  log "Instance terminated. Waiting for CloudTrail delivery (2 minutes)..."
  sleep 120
}

deploy_stack() {
  log "Installing infra deps (CDK) ..."
  (cd infra && npm install >/dev/null)
  log "CDK bootstrap (one-time per account/region)..."
  (cd infra && cdk bootstrap aws://"$ACCOUNT_ID"/"$REGION" || true)
  log "Deploying ${STACK_NAME}..."
  (cd infra && cdk deploy "$STACK_NAME" --outputs-file "$OUTPUTS_FILE" --require-approval never)
}

print_outputs() {
  if [ -f "$OUTPUTS_FILE" ]; then
    STATE_MACHINE_ARN=$(jq -r '."AlphaStack".AlphaStateMachineArn // empty' "$OUTPUTS_FILE")
    APPROVAL_TABLE=$(jq -r '."AlphaStack".ApprovalTableName // empty' "$OUTPUTS_FILE")
    BASELINE_TABLE=$(jq -r '."AlphaStack".BaselineTableName // empty' "$OUTPUTS_FILE")
    log "CDK outputs:"
    echo "  State Machine ARN : ${STATE_MACHINE_ARN}"
    echo "  Approval Table    : ${APPROVAL_TABLE}"
    echo "  Baseline Table    : ${BASELINE_TABLE}"
  else
    log "No outputs file found ($OUTPUTS_FILE)"
  fi
}

run_analyze_demo() {
  log "Installing python deps via uv..."
  UV_CACHE_DIR=.uv-cache uv sync --all-extras >/dev/null

  ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${DEMO_ROLE_NAME}"
  log "Running alpha analyze against ${ROLE_ARN} ..."
  UV_CACHE_DIR=.uv-cache uv run alpha analyze \
    --role-arn "$ROLE_ARN" \
    --usage-days 7 \
    --output proposal.json \
    --output-cloudformation cfn-patch.yml \
    --output-terraform tf-patch.tf
  log "Proposal ready: proposal.json (CFN: cfn-patch.yml, TF: tf-patch.tf)"
  log "Suggested next commands:"
  if [ -f "$OUTPUTS_FILE" ]; then
    STATE_MACHINE_ARN=$(jq -r '."AlphaStack".AlphaStateMachineArn // empty' "$OUTPUTS_FILE")
    echo "  Dry-run rollout: UV_CACHE_DIR=.uv-cache uv run alpha apply --state-machine-arn ${STATE_MACHINE_ARN} --proposal proposal.json --dry-run"
    echo "  Drift check   : BASELINE_TABLE_NAME=alpha-baselines UV_CACHE_DIR=.uv-cache uv run alpha drift --role-arn ${ROLE_ARN}"
  fi
}

cleanup() {
  log "Destroying CDK stack ${STACK_NAME}..."
  (cd infra && cdk destroy "$STACK_NAME" --force || true)
  log "Deleting demo role ${DEMO_ROLE_NAME}..."
  aws iam delete-role-policy --role-name "$DEMO_ROLE_NAME" --policy-name OverPermAdminLike >/dev/null 2>&1 || true
  aws iam delete-role --role-name "$DEMO_ROLE_NAME" >/dev/null 2>&1 || true
  log "Cleanup complete."
}

case "$ACTION" in
  apply)
    ensure_prereqs
    ensure_access_analyzer
    ensure_cloudtrail
    create_demo_role
    generate_role_usage
    deploy_stack
    print_outputs
    run_analyze_demo
    ;;
  cleanup)
    ensure_prereqs
    cleanup
    ;;
  *)
    echo "Usage: $0 [apply|cleanup]" >&2
    exit 1
    ;;
esac

log "Done."
