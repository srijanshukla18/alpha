# ALPHA Deployment Guide

This guide walks you through deploying ALPHA (Autonomous Least-Privilege Hardening Agent) to your AWS environment.

## Prerequisites

### Required Tools
- **Python 3.11+**: Core runtime for Lambda functions
- **Poetry**: Dependency management (`pip install poetry`)
- **AWS CLI**: Configured with credentials (`aws configure`)
- **AWS CDK**: Infrastructure deployment (`npm install -g aws-cdk`)
- **Node.js 18+**: Required for CDK

### Required AWS Permissions
The deploying IAM principal needs:
- CloudFormation full access
- Lambda create/update permissions
- IAM role creation permissions
- DynamoDB table creation
- Step Functions state machine creation
- S3 bucket access (for CDK assets)

### AWS Service Availability
Ensure the following services are available in your chosen region:
- Amazon Bedrock (with Claude 3.5 Sonnet model access)
- IAM Access Analyzer
- AWS Step Functions
- AWS Lambda
- Amazon DynamoDB

**Recommended Regions**: `us-east-1`, `us-west-2`, `eu-west-1`

## Quick Start (5 minutes)

For a fast demo deployment without customization:

```bash
# 1. Clone and install dependencies
cd alpha/
poetry install

# 2. Bootstrap CDK (first time only)
cd infra/
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=us-east-1
cdk bootstrap

# 3. Deploy infrastructure
pip install -r requirements.txt
cdk deploy --all --require-approval never

# 4. Note the outputs (DynamoDB table name, Step Functions ARN, etc.)
```

## Detailed Deployment Steps

### Step 1: Configure Environment

Create a `.env` file in the project root:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# Bedrock Configuration
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-5-20250929-v1:0
BEDROCK_TEMPERATURE=0.2

# Guardrail Configuration (comma-separated)
GUARDRAIL_BLOCKED_ACTIONS=iam:PassRole,sts:AssumeRole
GUARDRAIL_DISALLOWED_SERVICES=iam,sts
GUARDRAIL_REQUIRED_CONDITIONS={"StringEquals":{"aws:RequestedRegion":"us-east-1"}}

# Notifications (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# GitHub Integration (optional)
GITHUB_TOKEN=ghp_YourPersonalAccessToken
```

### Step 2: Install Dependencies

```bash
# Install Python package dependencies
poetry install

# Verify installation
poetry run python -c "import alpha_agent; print('ALPHA package installed successfully')"
```

### Step 3: Enable Bedrock Model Access

1. Navigate to AWS Console → Amazon Bedrock → Model access
2. Request access to **Anthropic Claude Sonnet 4.5** model
3. Wait for approval (usually instant for standard models)
4. Verify access:
   ```bash
   aws bedrock list-foundation-models \
     --query 'modelSummaries[?modelId==`anthropic.claude-sonnet-4-5-20250929-v1:0`]'
   ```

### Step 4: Create IAM Access Analyzer

ALPHA requires an IAM Access Analyzer analyzer in your account:

```bash
# Create analyzer (if not exists)
aws accessanalyzer create-analyzer \
  --analyzer-name alpha-analyzer \
  --type ACCOUNT \
  --region us-east-1

# Note the analyzer ARN
export ANALYZER_ARN=$(aws accessanalyzer list-analyzers \
  --region us-east-1 \
  --query 'analyzers[?name==`alpha-analyzer`].arn' \
  --output text)

echo "Analyzer ARN: $ANALYZER_ARN"
```

### Step 5: Deploy Infrastructure with CDK

```bash
cd infra/

# Install CDK dependencies
pip install -r requirements.txt

# Set deployment environment
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=us-east-1

# Bootstrap CDK (first time only per account/region)
cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/$CDK_DEFAULT_REGION

# Preview changes
cdk diff

# Deploy stack
cdk deploy AlphaStack --require-approval never

# Save outputs
cdk deploy AlphaStack --outputs-file ../outputs.json
```

**Expected Outputs**:
- `AlphaStack.ApprovalTableName` - DynamoDB table name
- `AlphaStack.StateMachineArn` - Step Functions state machine ARN
- `AlphaStack.GeneratePolicyFunctionArn` - Lambda function ARNs
- ... (other Lambda ARNs)

### Step 6: Configure CloudTrail Integration

ALPHA analyzes CloudTrail activity. Ensure you have an organization trail:

```bash
# Check existing trails
aws cloudtrail list-trails --region us-east-1

# Create trail if needed
aws cloudtrail create-trail \
  --name alpha-trail \
  --s3-bucket-name your-cloudtrail-bucket \
  --is-multi-region-trail \
  --enable-log-file-validation

aws cloudtrail start-logging --name alpha-trail
```

### Step 7: Test Deployment

Run a test execution of the ALPHA workflow:

```bash
# Use the demo CLI (simulated, no AWS calls)
poetry run python demo_cli.py --role-arn arn:aws:iam::$AWS_ACCOUNT_ID:role/test-role

# Or trigger a real Step Functions execution
aws stepfunctions start-execution \
  --state-machine-arn $(cat outputs.json | jq -r '.AlphaStack.StateMachineArn') \
  --input '{
    "analyzer_arn": "'"$ANALYZER_ARN"'",
    "resource_arn": "arn:aws:iam::'"$AWS_ACCOUNT_ID"':role/test-role",
    "cloudtrail_access_role_arn": "arn:aws:iam::'"$AWS_ACCOUNT_ID"':role/AlphaCloudTrailAccessRole",
    "cloudtrail_trail_arns": ["arn:aws:cloudtrail:us-east-1:'"$AWS_ACCOUNT_ID"':trail/alpha-trail"],
    "usage_period_days": 30,
    "context": {
      "roleArn": "arn:aws:iam::'"$AWS_ACCOUNT_ID"':role/test-role",
      "service_owner": "platform-team",
      "environment": "sandbox",
      "business_impact": "low"
    }
  }'
```

## AgentCore Deployment (Optional)

For agent-driven autonomous operation:

### Step 1: Install AgentCore SDK

```bash
poetry add bedrock-agentcore strands-agents
```

### Step 2: Deploy AgentCore Runtime

```bash
# Package Lambda layer with AgentCore dependencies
cd lambdas/agentcore_runtime/
zip -r agentcore-layer.zip .

# Create AgentCore runtime (via AWS Console or CLI)
# Note: AgentCore CLI tooling simplifies this process

# Register ALPHA tools with AgentCore Gateway
python -c "
from alpha_agent.agentcore import get_agentcore_tool_definitions
import json
print(json.dumps(get_agentcore_tool_definitions(), indent=2))
" > agentcore_tools.json

# Upload tool definitions to AgentCore Gateway (via Console)
```

### Step 3: Configure AgentCore Agent

Create `agentcore_config.json`:

```json
{
  "agent_name": "ALPHA",
  "description": "Autonomous Least-Privilege Hardening Agent for IAM policies",
  "runtime": {
    "function_arn": "arn:aws:lambda:us-east-1:123456789012:function:alpha-agentcore-runtime",
    "timeout": 900,
    "memory": 1024
  },
  "memory": {
    "strategy": "managed",
    "short_term_enabled": true,
    "long_term_enabled": true
  },
  "tools": [
    {
      "type": "gateway",
      "gateway_id": "alpha-tools"
    }
  ],
  "identity": {
    "role_arn": "arn:aws:iam::123456789012:role/AlphaAgentCoreRole"
  }
}
```

## Post-Deployment Configuration

### 1. Set Up Approval Workflow

#### Option A: Slack Integration

1. Create a Slack incoming webhook
2. Add webhook URL to Lambda environment variables:
   ```bash
   aws lambda update-function-configuration \
     --function-name alpha-approval-checker \
     --environment "Variables={SLACK_WEBHOOK_URL=https://hooks.slack.com/...}"
   ```

#### Option B: Manual DynamoDB Entries

To approve a proposal manually:

```bash
aws dynamodb put-item \
  --table-name alpha-approvals \
  --item '{
    "proposal_id": {"S": "arn:aws:iam::123456789012:role/test-role"},
    "timestamp": {"S": "2025-01-15T10:00:00Z"},
    "approved": {"BOOL": true},
    "approver": {"S": "admin@company.com"},
    "comments": {"S": "Approved after review"}
  }'
```

### 2. Configure Monitoring Alarms

```bash
# Create CloudWatch alarm for failed policy generations
aws cloudwatch put-metric-alarm \
  --alarm-name alpha-policy-generation-failures \
  --alarm-description "Alert on ALPHA policy generation failures" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=alpha-generate-policy \
  --evaluation-periods 1 \
  --treat-missing-data notBreaching
```

### 3. Set Up Periodic Execution (Optional)

Use EventBridge to run ALPHA on a schedule:

```bash
# Create rule for weekly analysis
aws events put-rule \
  --name alpha-weekly-analysis \
  --schedule-expression "cron(0 2 ? * MON *)" \
  --description "Run ALPHA analysis weekly"

# Add Step Functions as target
aws events put-targets \
  --rule alpha-weekly-analysis \
  --targets "Id"="1","Arn"="$(cat outputs.json | jq -r '.AlphaStack.StateMachineArn')","RoleArn"="arn:aws:iam::$AWS_ACCOUNT_ID:role/EventBridgeStepFunctionsRole"
```

## Verification & Testing

### 1. Verify Lambda Functions

```bash
# Test policy generation
aws lambda invoke \
  --function-name alpha-generate-policy \
  --payload '{
    "analyzer_arn": "'"$ANALYZER_ARN"'",
    "resource_arn": "arn:aws:iam::'"$AWS_ACCOUNT_ID"':role/test-role",
    "cloudtrail_access_role_arn": "arn:aws:iam::'"$AWS_ACCOUNT_ID"':role/AlphaCloudTrailAccessRole",
    "cloudtrail_trail_arns": ["arn:aws:cloudtrail:us-east-1:'"$AWS_ACCOUNT_ID"':trail/alpha-trail"],
    "usage_period_days": 7
  }' \
  /tmp/output.json

cat /tmp/output.json
```

### 2. Monitor Execution

```bash
# List recent Step Functions executions
aws stepfunctions list-executions \
  --state-machine-arn $(cat outputs.json | jq -r '.AlphaStack.StateMachineArn') \
  --max-results 5

# Get execution details
aws stepfunctions describe-execution \
  --execution-arn <execution-arn>
```

### 3. Check Logs

```bash
# View Lambda logs
aws logs tail /aws/lambda/alpha-generate-policy --follow

# View Step Functions logs
aws logs tail /aws/stepfunctions/alpha --follow
```

## Troubleshooting

### Common Issues

#### Issue: "Access Denied" when calling IAM Access Analyzer

**Solution**: Ensure the Lambda execution role has `access-analyzer:StartPolicyGeneration` and `access-analyzer:GetGeneratedPolicy` permissions.

```bash
aws iam put-role-policy \
  --role-name AlphaLambdaRole \
  --policy-name AccessAnalyzerPolicy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": [
        "access-analyzer:StartPolicyGeneration",
        "access-analyzer:GetGeneratedPolicy"
      ],
      "Resource": "*"
    }]
  }'
```

#### Issue: "Model not found" when invoking Bedrock

**Solution**: Verify model access is enabled and model ID is correct.

```bash
# List available models
aws bedrock list-foundation-models \
  --query 'modelSummaries[?contains(modelId, `claude`)].modelId'

# Update Lambda environment variable if needed
aws lambda update-function-configuration \
  --function-name alpha-bedrock-reasoner \
  --environment "Variables={BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-5-20250929-v1:0}"
```

#### Issue: Policy generation job times out

**Solution**: Increase Lambda timeout and ensure CloudTrail has sufficient data.

```bash
# Increase timeout to 15 minutes
aws lambda update-function-configuration \
  --function-name alpha-generate-policy \
  --timeout 900
```

#### Issue: Step Functions execution stuck in "WaitForApproval" loop

**Solution**: Manually approve the proposal in DynamoDB (see "Manual DynamoDB Entries" above).

## Cleanup

To remove all ALPHA infrastructure:

```bash
# Delete CDK stack
cd infra/
cdk destroy AlphaStack

# Delete CloudTrail (if created by ALPHA)
aws cloudtrail delete-trail --name alpha-trail

# Delete S3 buckets (if applicable)
aws s3 rb s3://alpha-cloudtrail-bucket --force
```

## Security Best Practices

1. **Use Secrets Manager**: Store Slack webhooks and GitHub tokens in Secrets Manager, not environment variables
2. **Enable MFA**: Require MFA for approval actions
3. **Audit Logs**: Enable CloudTrail logging for all ALPHA API calls
4. **Least Privilege**: Scope IAM permissions to specific resources (not `Resource: "*"`)
5. **VPC Deployment**: Deploy Lambdas in VPC for network isolation (if required by compliance)
6. **Encryption**: Use KMS customer-managed keys for DynamoDB and S3

## Cost Estimates

For a typical organization with 100 IAM roles analyzed monthly:

| Service              | Usage                          | Est. Monthly Cost |
|----------------------|--------------------------------|-------------------|
| IAM Access Analyzer  | 100 policy generation jobs     | $5.00             |
| Amazon Bedrock       | 100 Claude invocations         | $3.00             |
| AWS Lambda           | 500 executions, 512MB, 3min avg| $2.50             |
| DynamoDB             | 1000 reads/writes              | $0.25             |
| Step Functions       | 100 executions, 10 steps each  | $0.25             |
| CloudWatch Logs      | 5 GB stored                    | $2.50             |
| **Total**            |                                | **~$13.50/month** |

**Note**: AgentCore has separate pricing during GA (free trial until Sept 2025).

## Next Steps

- [Architecture Documentation](./ARCHITECTURE.md)
- [Demo Video Script](./DEMO_SCRIPT.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [Hackathon Submission Checklist](./SUBMISSION_CHECKLIST.md)
