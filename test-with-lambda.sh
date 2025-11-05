#!/bin/bash
# Create a test Lambda role, simulate usage, then analyze it
# This proves ALPHA works end-to-end

set -e

echo "=========================================="
echo "ALPHA - End-to-End Test with Real Lambda"
echo "=========================================="
echo ""

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ AWS credentials not configured"
    exit 1
fi

REGION=${AWS_REGION:-us-east-1}
ROLE_NAME="AlphaTestRole-$(date +%s)"
LAMBDA_NAME="AlphaTestLambda-$(date +%s)"

echo "Creating test resources:"
echo "  Region: $REGION"
echo "  Role: $ROLE_NAME"
echo "  Lambda: $LAMBDA_NAME"
echo ""

# Create IAM role with broad permissions
echo "1. Creating IAM role with AdminAccess (intentionally over-privileged)..."
TRUST_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)

aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "$TRUST_POLICY" \
    --description "Test role for ALPHA - will be deleted" \
    > /dev/null

aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/AdministratorAccess"

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
echo "✓ Created role: $ROLE_ARN"

# Wait for IAM role to propagate
echo "  Waiting 10s for IAM to propagate..."
sleep 10

# Create Lambda function that only uses S3 and CloudWatch
echo ""
echo "2. Creating Lambda function (only uses S3 + CloudWatch)..."

LAMBDA_CODE=$(cat <<'EOF'
import boto3
import json

def lambda_handler(event, context):
    # This Lambda only uses S3 and CloudWatch Logs
    # Even though it has AdminAccess!

    s3 = boto3.client('s3')

    # List some buckets
    response = s3.list_buckets()

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Test Lambda - only uses S3',
            'bucket_count': len(response['Buckets'])
        })
    }
EOF
)

# Create zip file
TMP_DIR=$(mktemp -d)
echo "$LAMBDA_CODE" > "$TMP_DIR/lambda_function.py"
(cd "$TMP_DIR" && zip -q lambda.zip lambda_function.py)

aws lambda create-function \
    --function-name "$LAMBDA_NAME" \
    --runtime python3.11 \
    --role "$ROLE_ARN" \
    --handler lambda_function.lambda_handler \
    --zip-file "fileb://$TMP_DIR/lambda.zip" \
    --region "$REGION" \
    > /dev/null

rm -rf "$TMP_DIR"
echo "✓ Created Lambda: $LAMBDA_NAME"

# Invoke Lambda a few times to generate CloudTrail activity
echo ""
echo "3. Invoking Lambda to generate CloudTrail activity..."
for i in {1..3}; do
    aws lambda invoke \
        --function-name "$LAMBDA_NAME" \
        --region "$REGION" \
        /tmp/lambda-output.json \
        > /dev/null 2>&1 || true
    echo "  Invocation $i/3"
    sleep 2
done

echo "✓ Lambda invoked 3 times"

# Wait for CloudTrail to process events
echo ""
echo "4. Waiting 30s for CloudTrail to process events..."
echo "  (CloudTrail typically has 5-15 minute delay, but we'll try anyway)"
sleep 30

# Run ALPHA analysis
echo ""
echo "=========================================="
echo "5. Running ALPHA Analysis"
echo "=========================================="

OUTPUT_DIR="./test-lambda-output"
mkdir -p "$OUTPUT_DIR"

echo "Analyzing role: $ROLE_ARN"
echo ""

if poetry run alpha analyze \
    --role-arn "$ROLE_ARN" \
    --usage-days 1 \
    --guardrails none \
    --output "$OUTPUT_DIR/proposal.json" \
    --output-terraform "$OUTPUT_DIR/policy.tf"; then

    echo ""
    echo "=========================================="
    echo "✓ Analysis Complete!"
    echo "=========================================="
    echo ""

    if command -v jq &> /dev/null; then
        echo "Expected: Lambda should only need S3 and Logs permissions"
        echo "Current: Has AdministratorAccess (all permissions)"
        echo ""
        echo "ALPHA found these used actions:"
        jq -r '.proposal.proposedPolicy.Statement[].Action[]' "$OUTPUT_DIR/proposal.json" | sort | uniq
        echo ""
        echo "Policy changes:"
        jq -r '.diff' "$OUTPUT_DIR/proposal.json"
        echo ""
    fi

    echo "Full output in: $OUTPUT_DIR/"
    echo ""
fi

# Cleanup
echo "=========================================="
echo "Cleanup"
echo "=========================================="
read -p "Delete test resources? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Deleting Lambda..."
    aws lambda delete-function --function-name "$LAMBDA_NAME" --region "$REGION" 2>/dev/null || true

    echo "Detaching policies from role..."
    aws iam detach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/AdministratorAccess" 2>/dev/null || true

    echo "Deleting role..."
    aws iam delete-role --role-name "$ROLE_NAME" 2>/dev/null || true

    echo "✓ Cleaned up test resources"
else
    echo ""
    echo "⚠️  Remember to manually delete:"
    echo "  Lambda: $LAMBDA_NAME"
    echo "  IAM Role: $ROLE_NAME"
    echo ""
    echo "Commands:"
    echo "  aws lambda delete-function --function-name $LAMBDA_NAME --region $REGION"
    echo "  aws iam detach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/AdministratorAccess"
    echo "  aws iam delete-role --role-name $ROLE_NAME"
fi

echo ""
echo "=========================================="
echo "Test Complete"
echo "=========================================="
echo ""
echo "Note: CloudTrail has 5-15 min delay. If ALPHA found no events,"
echo "wait a bit and run:"
echo "  poetry run alpha analyze --role-arn $ROLE_ARN --usage-days 1"
