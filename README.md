# ALPHA - IAM Least-Privilege Policy Generator

Automatically generate least-privilege IAM policies based on actual CloudTrail usage.

## The Problem

- 95% of IAM permissions are never used in production
- Roles have `AdminAccess` or `*` wildcards everywhere
- Manual policy audits take weeks  
- Fear of breaking production prevents fixes

## The Solution

ALPHA scans CloudTrail to see what IAM actions a role **actually uses**, then generates a tight policy with only those permissions.

**Simple workflow:**
1. Analyze: Scan CloudTrail for a role's actual usage
2. Review: Get a least-privilege policy + risk assessment
3. Apply: Use the generated CloudFormation/Terraform patches

## Quick Start

### Install

```bash
# Clone and install
git clone https://github.com/YOUR_ORG/alpha.git
cd alpha
poetry install
```

### Prerequisites

- Python 3.11+
- AWS credentials configured
- CloudTrail enabled in your account
- (Optional) Amazon Bedrock model access for AI reasoning

### Basic Usage

```bash
# Analyze a role
export ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT:role/YourRole

poetry run alpha analyze \
  --role-arn "$ROLE_ARN" \
  --output proposal.json

# View the results
cat proposal.json | jq '.proposal.rationale'
cat proposal.json | jq '.diff'
```

### With All Output Formats

```bash
poetry run alpha analyze \
  --role-arn "$ROLE_ARN" \
  --output proposal.json \
  --output-cloudformation cfn-patch.yml \
  --output-terraform tf-patch.tf

# Now you have patches ready to apply to your infrastructure
```

## How It Works

1. **Scans CloudTrail** - Uses CloudTrail Event History API to see what actions the role performed (configurable time window, default 30 days)

2. **Generates Policy** - Creates an IAM policy with only the observed actions, grouped by service

3. **AI Reasoning (Optional)** - If you have Bedrock access, uses Claude/Nova to:
   - Add edge-case permissions (e.g., missing `ListBucket` when `GetObject` is used)
   - Assess break risk
   - Suggest safer conditions

4. **Enforces Guardrails** - Removes dangerous patterns:
   - Blocks wildcards (`iam:*`, `s3:*`)
   - Blocks sensitive actions (`iam:PassRole`, `sts:AssumeRole`)
   - Enforces conditions (e.g., region locks)

5. **Outputs Results** - Provides ready-to-use patches in multiple formats

## Commands

### analyze

Analyze an IAM role and generate a least-privilege policy.

```bash
poetry run alpha analyze --role-arn <ARN> [OPTIONS]
```

**Options:**
- `--role-arn` (required) - IAM role ARN to analyze
- `--usage-days N` - Days of CloudTrail to scan (default: 30)
- `--output FILE` - Save proposal JSON
- `--output-cloudformation FILE` - Save CloudFormation patch
- `--output-terraform FILE` - Save Terraform patch
- `--guardrails {none|sandbox|prod}` - Guardrail level (default: prod)
- `--exclude-services SERVICES` - Comma-separated services to exclude
- `--suppress-actions ACTIONS` - Comma-separated actions to block
- `--bedrock-model MODEL_ID` - Override Bedrock model

**Examples:**

```bash
# Basic analysis
poetry run alpha analyze --role-arn arn:aws:iam::123:role/MyRole --output proposal.json

# Different time window
poetry run alpha analyze --role-arn $ROLE_ARN --usage-days 7 --output proposal.json

# Less strict guardrails
poetry run alpha analyze --role-arn $ROLE_ARN --guardrails sandbox --output proposal.json

# Exclude specific services
poetry run alpha analyze --role-arn $ROLE_ARN --exclude-services ec2,rds --output proposal.json

# Use Nova Pro instead of Claude
poetry run alpha analyze --role-arn $ROLE_ARN --bedrock-model us.amazon.nova-pro-v1:0
```

### propose

Create a GitHub pull request with the policy changes.

```bash
poetry run alpha propose --repo <ORG/REPO> --branch <BRANCH> --input proposal.json
```

**Options:**
- `--repo` (required) - GitHub repository (e.g., `myorg/infrastructure`)
- `--branch` (required) - Branch name for the PR
- `--input` (required) - Proposal JSON from analyze command
- `--base` - Base branch (default: main)
- `--title` - Custom PR title
- `--draft` - Create as draft PR
- `--github-token` - GitHub token (or set `GITHUB_TOKEN` env var)

**Example:**

```bash
export GITHUB_TOKEN=ghp_your_token

poetry run alpha propose \
  --repo myorg/infrastructure \
  --branch alpha/harden-ci-role \
  --input proposal.json
```

## Guardrail Presets

### none
No restrictions. Use for experimentation only.

### sandbox
- Blocks: `iam:PassRole`

### prod (default)
- Blocks: `iam:*`, `sts:AssumeRole`
- Requires: `StringEquals: { aws:RequestedRegion: us-east-1 }`
- Disallows services: `iam`, `organizations`

## Exit Codes (CI/CD Integration)

ALPHA uses exit codes to gate CI pipelines:

- **0** - Success, safe to proceed
- **1** - Tool error (bad arguments, AWS API failure, etc.)
- **2** - High risk (>10% break probability according to Bedrock)
- **3** - Guardrail violation (policy blocked by safety rules)

**Example CI usage:**

```yaml
- name: Analyze IAM Role
  run: |
    poetry run alpha analyze \
      --role-arn ${{ env.ROLE_ARN }} \
      --guardrails prod \
      --output proposal.json

- name: Block if risky
  if: ${{ failure() }}
  run: echo "Policy too risky or violates guardrails"
```

## Bedrock Models

### Default: Anthropic Claude Sonnet 4.5

ALPHA uses Claude for reasoning by default. Enable it in Bedrock Console → Model Access.

### Using Amazon Nova Pro

```bash
export ALPHA_BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
poetry run alpha analyze --role-arn $ROLE_ARN
```

Or via CLI:
```bash
poetry run alpha analyze --role-arn $ROLE_ARN --bedrock-model us.amazon.nova-pro-v1:0
```

### Graceful Fallback

If Bedrock is unavailable or not configured, ALPHA still works - it just uses CloudTrail data without AI reasoning.

## Troubleshooting

### "No CloudTrail events found"

The role hasn't been used recently. Try:
- Shorter time window: `--usage-days 1`
- Ensure CloudTrail is enabled and logging
- Check the role has been used in the specified region

### "AWS credentials not configured"

```bash
aws configure
# OR
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
```

### "Bedrock access denied"

ALPHA works without Bedrock, but to enable AI reasoning:
1. Go to AWS Bedrock Console → Model Access
2. Enable Claude Sonnet 4.5 or Nova Pro
3. Grant your IAM principal `bedrock:InvokeModel` permission

### "Exit code 2 (risky)"

Bedrock assessed >10% break probability. Review the risk assessment:

```bash
cat proposal.json | jq '.proposal.riskSignal'
cat proposal.json | jq '.proposal.remediationNotes'
```

### "Exit code 3 (guardrail violation)"

The generated policy contains blocked actions. Options:

```bash
# Use less strict guardrails
poetry run alpha analyze --role-arn $ROLE_ARN --guardrails sandbox

# Suppress specific actions
poetry run alpha analyze --role-arn $ROLE_ARN --suppress-actions iam:PassRole
```

## Cost Estimate

**Per role analysis:**
- CloudTrail Event History API: Free
- Bedrock inference (Claude/Nova): ~$0.03-0.05 per analysis
- IAM API calls: Free

**Total: ~$0.05 per role** (or $0 if not using Bedrock)

## Security

- ALPHA never modifies IAM policies directly - it only generates proposals
- All operations are read-only except for optional GitHub PR creation
- Guardrails enforce organizational security requirements
- Exit codes enable CI gating to prevent risky deployments

## Requirements

- Python 3.11+
- AWS credentials with:
  - `cloudtrail:LookupEvents`
  - `iam:GetRole`, `iam:GetRolePolicy`, `iam:ListRolePolicies`
  - `bedrock:InvokeModel` (optional, for AI reasoning)
- CloudTrail enabled in the account
- (Optional) Bedrock model access for AI features
- (Optional) GitHub token for PR creation

## License

MIT

---

**Stop over-privileged IAM roles. Generate least-privilege policies from actual usage.**
