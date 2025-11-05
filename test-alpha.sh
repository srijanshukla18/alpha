#!/bin/bash
# Test ALPHA against your AWS account
# This script is READ-ONLY - it won't modify any IAM policies

set -e

echo "=========================================="
echo "ALPHA - Quick Test Script"
echo "=========================================="
echo ""

# Check prerequisites
echo "1. Checking prerequisites..."
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Install it first: https://aws.amazon.com/cli/"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "⚠️  jq not found (optional but recommended). Install: apt-get install jq"
fi

# Verify AWS credentials
echo "2. Verifying AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Run: aws configure"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "✓ Connected to AWS account: $ACCOUNT_ID"
echo ""

# List IAM roles
echo "3. Fetching IAM roles in your account..."
ROLES=$(aws iam list-roles --query 'Roles[?starts_with(RoleName, `AWSServiceRole`) == `false`].{Name:RoleName, ARN:Arn}' --output json)
ROLE_COUNT=$(echo "$ROLES" | jq 'length')

if [ "$ROLE_COUNT" -eq 0 ]; then
    echo "❌ No IAM roles found in your account"
    exit 1
fi

echo "Found $ROLE_COUNT roles (excluding AWS service-linked roles)"
echo ""
echo "Common roles to test:"
echo "$ROLES" | jq -r '.[] | "  - \(.Name)"' | head -10

echo ""
echo "=========================================="
echo "Select a role to analyze (or press Enter to skip)"
echo "=========================================="
read -p "Role name: " ROLE_NAME

if [ -z "$ROLE_NAME" ]; then
    # Use first non-service-linked role
    ROLE_NAME=$(echo "$ROLES" | jq -r '.[0].Name')
    echo "Using first available role: $ROLE_NAME"
fi

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

echo ""
echo "=========================================="
echo "Running ALPHA Analysis"
echo "=========================================="
echo "Role: $ROLE_ARN"
echo "Time window: 30 days"
echo ""

# Create output directory
OUTPUT_DIR="./test-output"
mkdir -p "$OUTPUT_DIR"

# Run ALPHA
echo "⚡ Analyzing (this takes ~5 seconds)..."
if poetry run alpha analyze \
    --role-arn "$ROLE_ARN" \
    --usage-days 30 \
    --guardrails sandbox \
    --output "$OUTPUT_DIR/proposal.json" \
    --output-terraform "$OUTPUT_DIR/policy.tf" \
    --output-cloudformation "$OUTPUT_DIR/policy.yml"; then

    echo ""
    echo "=========================================="
    echo "✓ Analysis Complete!"
    echo "=========================================="
    echo ""
    echo "Output files created in: $OUTPUT_DIR/"
    echo "  - proposal.json (full analysis)"
    echo "  - policy.tf (Terraform)"
    echo "  - policy.yml (CloudFormation)"
    echo ""

    if command -v jq &> /dev/null; then
        echo "Quick Summary:"
        echo ""
        echo "Rationale:"
        jq -r '.proposal.rationale' "$OUTPUT_DIR/proposal.json"
        echo ""
        echo "Policy Changes:"
        jq -r '.diff.changeSummary' "$OUTPUT_DIR/proposal.json"
        echo ""
        echo "Guardrail Violations:"
        VIOLATIONS=$(jq '.proposal.guardrailViolations | length' "$OUTPUT_DIR/proposal.json")
        if [ "$VIOLATIONS" -eq 0 ]; then
            echo "  ✓ None"
        else
            jq -r '.proposal.guardrailViolations[] | "  ⚠️  \(.code): \(.message)"' "$OUTPUT_DIR/proposal.json"
        fi
        echo ""
    fi

    echo "View full proposal:"
    echo "  cat $OUTPUT_DIR/proposal.json | jq"
    echo ""
    echo "View Terraform:"
    echo "  cat $OUTPUT_DIR/policy.tf"
    echo ""

else
    echo ""
    echo "❌ Analysis failed. Check the error above."
    exit 1
fi

echo "=========================================="
echo "Test Complete"
echo "=========================================="
echo ""
echo "Note: This was READ-ONLY. No IAM policies were modified."
echo "Review the outputs in $OUTPUT_DIR/ before applying any changes."
