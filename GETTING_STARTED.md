# Getting Started with ALPHA

ALPHA analyzes your IAM roles and generates least-privilege policies based on actual CloudTrail usage.

## What Works Right Now

✅ **Core Features (Production Ready)**
- Fast IAM policy analysis using CloudTrail (finishes in seconds)
- AI-powered policy reasoning using Amazon Bedrock (optional, with fallback)
- Guardrails enforcement (block risky actions, enforce conditions)
- Multiple output formats (JSON, CloudFormation, Terraform)
- GitHub PR creation
- Offline demo mode for testing

## Quick Start (2 minutes)

### 1. Install

```bash
poetry install
```

### 2. Try it (no AWS needed!)

```bash
# Judge mode = offline demo with mock data
poetry run alpha analyze \
  --role-arn arn:aws:iam::123456789012:role/TestRole \
  --judge-mode \
  --output proposal.json

# View the results
cat proposal.json | head -40
```

### 3. Use with Real AWS

```bash
# Prerequisites:
# - AWS credentials configured (aws sts get-caller-identity should work)
# - CloudTrail enabled in your account
# - (Optional) Bedrock model access enabled

export ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT:role/YourRole

# Analyze a role
poetry run alpha analyze \
  --role-arn "$ROLE_ARN" \
  --usage-days 7 \
  --output proposal.json \
  --output-cloudformation cfn-patch.yml \
  --output-terraform tf-patch.tf

# Review the proposal
cat proposal.json | jq '.proposal.rationale'
cat proposal.json | jq '.proposal.riskSignal'
cat proposal.json | jq '.diff'
```

## How It Works

1. **Collects usage** - Scans CloudTrail Event History to see what actions the role actually performed
2. **Generates policy** - Creates a least-privilege policy with only the used actions
3. **AI reasoning** (optional) - Uses Bedrock to add edge-case permissions and assess risk
4. **Enforces guardrails** - Removes wildcards, blocks dangerous actions, enforces conditions
5. **Outputs results** - Saves JSON, CloudFormation, and Terraform patches ready to use

## Command Reference

### Basic Analysis

```bash
# Fast mode (default, seconds)
poetry run alpha analyze --role-arn "$ROLE_ARN" --output proposal.json

# With all output formats
poetry run alpha analyze \
  --role-arn "$ROLE_ARN" \
  --output proposal.json \
  --output-cloudformation cfn-patch.yml \
  --output-terraform tf-patch.tf

# Different guardrail levels
poetry run alpha analyze --role-arn "$ROLE_ARN" --guardrails sandbox  # Less strict
poetry run alpha analyze --role-arn "$ROLE_ARN" --guardrails prod     # Strict (default)
poetry run alpha analyze --role-arn "$ROLE_ARN" --guardrails none     # No restrictions

# Exclude specific services
poetry run alpha analyze \
  --role-arn "$ROLE_ARN" \
  --exclude-services ec2,rds \
  --suppress-actions s3:DeleteBucket

# Use different time windows
poetry run alpha analyze --role-arn "$ROLE_ARN" --usage-days 1   # Last day
poetry run alpha analyze --role-arn "$ROLE_ARN" --usage-days 90  # Last 3 months
```

### Create GitHub PR

```bash
export GITHUB_TOKEN=ghp_your_token

poetry run alpha propose \
  --repo YOUR_ORG/YOUR_REPO \
  --branch alpha/harden-role \
  --input proposal.json
```

### CI/CD Integration

ALPHA uses exit codes for pipeline gating:
- **0** = Safe to proceed
- **1** = Tool error
- **2** = High risk (>10% break probability)
- **3** = Guardrail violation

```bash
# In your CI pipeline
poetry run alpha analyze --role-arn "$ROLE_ARN" --guardrails prod --output proposal.json
if [ $? -ge 2 ]; then
  echo "❌ Policy too risky or violates guardrails"
  exit 1
fi
```

## Guardrail Presets

### none
No restrictions (use for experimentation)

### sandbox
- Blocks: `iam:PassRole`

### prod (default)
- Blocks: `iam:*`, `sts:AssumeRole`
- Requires: `StringEquals: { aws:RequestedRegion: us-east-1 }`
- Disallows services: `iam`, `organizations`

## Bedrock Models

Default: Anthropic Claude Sonnet 4.5

To use Amazon Nova Pro:
```bash
export ALPHA_BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
poetry run alpha analyze --role-arn "$ROLE_ARN"
```

Or via CLI:
```bash
poetry run alpha analyze \
  --role-arn "$ROLE_ARN" \
  --bedrock-model us.amazon.nova-pro-v1:0
```

**Note**: If Bedrock is unavailable or you don't have model access, ALPHA gracefully falls back and still produces useful outputs.

## Troubleshooting

### "No CloudTrail events found"

Your role hasn't been used recently. Try:
```bash
poetry run alpha analyze --role-arn "$ROLE_ARN" --usage-days 1  # Shorter window
poetry run alpha analyze --role-arn "$ROLE_ARN" --judge-mode    # Or use demo mode
```

### "AWS credentials not configured"

```bash
aws configure
# OR
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
```

### "Exit code 2 (risky)"

Bedrock assessed >10% break probability. Review:
```bash
cat proposal.json | jq '.proposal.riskSignal'
cat proposal.json | jq '.proposal.remediationNotes'
```

### "Exit code 3 (guardrail violation)"

Policy contains blocked actions. Options:
```bash
# Use less strict guardrails
poetry run alpha analyze --role-arn "$ROLE_ARN" --guardrails sandbox

# Or suppress specific actions
poetry run alpha analyze --role-arn "$ROLE_ARN" --suppress-actions iam:PassRole
```

## What's NOT Included (Yet)

The following features exist in code but are not tested/production-ready:
- Access Analyzer mode (slower, more detailed resource scoping)
- Step Functions rollout automation
- DynamoDB approval workflows
- Lambda-based orchestration
- Full CDK infrastructure deployment

Use at your own risk or contribute to finish them!

## Cost Estimate

- **Judge mode**: $0 (offline)
- **Real analysis per role**: ~$0.25
  - CloudTrail Event History: Free
  - Bedrock (Claude/Nova): ~$0.03-0.05 per analysis
  - IAM API calls: Free

## Next Steps

1. ✅ Try judge mode to learn the tool
2. ✅ Analyze a non-critical role in your account
3. ✅ Review the proposal carefully
4. ✅ Apply changes manually to CloudFormation/Terraform
5. ⚠️  Don't apply policies blindly - review diffs first!

## Support

- Issues: https://github.com/YOUR_ORG/alpha/issues
- Documentation: See README.md for full details

---

**Built for AWS AI Agent Hackathon 2025**
