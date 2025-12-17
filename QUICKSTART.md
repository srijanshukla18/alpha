# Quickstart

## Prerequisites

```bash
# 1. Python version
python3 --version  # Need 3.11+

# 2. AWS credentials configured
aws sts get-caller-identity  # Should show your account ID

# 3. Poetry installed
poetry --version  # If not: curl -sSL https://install.python-poetry.org | python3 -
```

## Install ALPHA

```bash
# from the repo root
poetry install
```

## Option A: Fast Mode (default, no analyzer wait)

Best for CI and live demos. Uses CloudTrail Event History; finishes in seconds.

```bash
export TARGET_ROLE=arn:aws:iam::YOUR_ACCOUNT:role/YourRole
poetry run alpha analyze \
  --role-arn "$TARGET_ROLE" \
  --usage-days 7 \
  --guardrails sandbox \
  --output proposal.json \
  --output-cloudformation cfn-patch.yml \
  --output-terraform tf-patch.tf

# Check what was generated
ls -lh proposal.json cfn-patch.yml tf-patch.tf
cat proposal.json | head -20
```

Notes
- To force Analyzer mode, add `--no-fast`.
- If Bedrock model access isn’t enabled, ALPHA falls back and still emits outputs.

## Option B: Judge Mode (offline, deterministic)

Great for offline demos; no AWS calls; same output every time.

```bash
poetry run alpha analyze \
  --role-arn arn:aws:iam::123456789012:role/TestRole \
  --judge-mode \
  --output proposal.json \
  --output-cloudformation cfn-patch.yml \
  --output-terraform tf-patch.tf
```

## Option C: Analyzer Mode (resource‑scoped; slower)

Provision Access Analyzer + CloudTrail trails, then run without fast mode.

Required IAM actions: `access-analyzer:StartPolicyGeneration`, `access-analyzer:GetGeneratedPolicy`, `cloudtrail:LookupEvents`, `iam:GetRole*`, `bedrock:InvokeModel`.

Run

```bash
poetry run alpha analyze \
  --role-arn "$TARGET_ROLE" \
  --no-fast \
  --usage-days 7 \
  --guardrails prod \
  --timeout-seconds 1800 \
  --output proposal.json
```

## Bedrock Models (Claude or Nova Pro)

Default model is Anthropic Sonnet 4.5. To use Nova Pro:

```bash
export ALPHA_BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
```

Enable the chosen model in Bedrock Console → Model access. Grant your user/role `bedrock:InvokeModel` on the inference profile/resource.

**Fallback:** If Bedrock is unavailable or not enabled, ALPHA still emits outputs with a conservative risk signal.

## Review the proposal

```bash
# See the summary
cat proposal.json | jq '.proposal.rationale'
cat proposal.json | jq '.proposal.riskSignal'

# See the new policy
cat proposal.json | jq '.proposal.proposedPolicy'

# See what changed
cat proposal.json | jq '.diff'
```

## Full Workflow (Analyze → PR → Deploy)

### Prerequisites for Full Flow

1. **GitHub repo with IAM policies** (Terraform/CloudFormation)
2. **GITHUB_TOKEN** environment variable
3. **Step Functions state machine** (deploy with CDK first)

### Deploy rollout infrastructure (optional)

```bash
cd infra
npm install
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=us-east-1
cdk bootstrap  # First time only
cdk deploy AlphaStack
```

Creates: Step Functions state machine for staged rollouts, Lambdas (guardrails, rollout), DynamoDB approvals, CloudWatch dashboards.

**Save the state machine ARN from CDK output:**

```bash
export STATE_MACHINE_ARN="arn:aws:states:us-east-1:YOUR_ACCOUNT:stateMachine/AlphaRollout"
```

### Full Workflow

```bash
# 1. Analyze
poetry run alpha analyze \
  --role-arn "$TARGET_ROLE" \
  --usage-days 30 \
  --output proposal.json \
  --guardrails prod

# 2. Create GitHub PR (if you have a repo)
export GITHUB_TOKEN=ghp_YOUR_TOKEN
poetry run alpha propose \
  --repo YOUR_ORG/YOUR_INFRA_REPO \
  --branch "alpha/harden-$(date +%s)" \
  --input proposal.json

# 3. Apply (dry-run first!)
poetry run alpha apply \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --proposal proposal.json \
  --dry-run

# 4. Actually apply (after reviewing dry-run output)
poetry run alpha apply \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --proposal proposal.json \
  --environment sandbox \
  --canary 10
```

## Optional: Step Functions rollout demo

Deploy a minimal state machine (all Pass states) using the provided definition (role must trust `states.amazonaws.com` and have Step Functions execution permissions):

```bash
aws iam create-role \
  --role-name AlphaStepFunctionsRole \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"states.amazonaws.com"},"Action":"sts:AssumeRole"}]}' || true

aws iam attach-role-policy \
  --role-name AlphaStepFunctionsRole \
  --policy-arn arn:aws:iam::aws:policy/AWSStepFunctionsFullAccess || true

aws stepfunctions create-state-machine \
  --name AlphaMinimalRollout \
  --definition file://workflows/minimal_state_machine.asl.json \
  --role-arn arn:aws:iam::YOUR_ACCOUNT:role/AlphaStepFunctionsRole

export STATE_MACHINE_ARN=arn:aws:states:us-east-1:YOUR_ACCOUNT:stateMachine:AlphaMinimalRollout

poetry run alpha apply \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --proposal proposal.json \
  --dry-run

poetry run alpha apply \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --proposal proposal.json
```

`alpha apply` defaults to `--require-approval False`. Add `--require-approval --approval-table <table>` once approvals are wired.

## Optional: AgentCore Runtime (deploy primitives)

Deploy ALPHA primitives as managed endpoints using the provided entrypoint module (single entrypoint with `action` key):

```bash
# Use the entrypoint shipped with ALPHA
# Bootstrap a uv project for AgentCore (one-time)
./scripts/bootstrap_agentcore.sh agentcore_deploy

# Configure and launch using that directory
uv --directory agentcore_deploy run agentcore configure -e src/alpha_agent/agentcore_entrypoint.py
uv --directory agentcore_deploy run agentcore launch
uv --directory agentcore_deploy run agentcore status

# Invoke examples
uv --directory agentcore_deploy run agentcore invoke '{"action":"analyze_fast_policy","roleArn":"'$ROLE_ARN'","usageDays":1,"region":"'$AWS_REGION'"}'
uv --directory agentcore_deploy run agentcore invoke '{"action":"enforce_policy_guardrails","policy":{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"s3:*","Resource":"*"}]},"preset":"prod"}'
```

## Troubleshooting

### "Access Analyzer not found" (Analyzer mode)
Create analyzer first:
`aws accessanalyzer create-analyzer --analyzer-name default --type ACCOUNT --region us-east-1`

### "Bedrock access denied"
Enable the specific model (Anthropic/Nova) in Bedrock → Model access; ensure your principal has `bedrock:InvokeModel`.

### "No CloudTrail events found"
The role may have no recent activity. Try `--usage-days 1`, or use judge mode.

### "Exit code 2 (risky)"
Bedrock estimated >10% break probability. Review:

```bash
cat proposal.json | jq '.proposal.riskSignal'
cat proposal.json | jq '.proposal.remediationNotes'
```

### "Exit code 3 (guardrail violation)"
Generated policy contains blocked actions. Review:

```bash
cat proposal.json | jq '.proposal.guardrailViolations'
```

Options:
- Use less strict preset: `--guardrails sandbox` or `--guardrails none`
- Suppress specific actions: `--suppress-actions iam:PassRole`

## Cost Estimate

**Judge mode:** $0 (no AWS calls)

**Real mode per role:**
- IAM Access Analyzer: ~$0.20 (GeneratePolicy API)
- Bedrock Claude Sonnet 4.5: ~$0.03-0.05 (input: 2K tokens, output: 1K tokens)
- CloudTrail: Free (LookupEvents API)
- **Total: ~$0.25 per role analysis**

**Infrastructure (if deployed):**
- Step Functions: $0.025 per 1000 state transitions
- Lambda: Free tier covers most usage
- DynamoDB: On-demand, ~$0.01/month for approval table
- **Total: <$5/month even with heavy usage**

## Quick Reference

```bash
# Judge mode (offline, instant, $0)
poetry run alpha analyze --role-arn arn:aws:iam::123:role/Test --judge-mode

# Real analysis (30-90s, ~$0.25)
poetry run alpha analyze --role-arn "$ROLE_ARN" --output proposal.json

# Check for drift (Day 2 Ops)
poetry run alpha diff --input proposal.json

# Monitor rollout status
poetry run alpha status --role-arn "$ROLE_ARN" --state-machine-arn "$ARN"

# Emergency rollback
poetry run alpha rollback --proposal proposal.json --state-machine-arn "$ARN"

# With all outputs
poetry run alpha analyze \
  --role-arn "$ROLE_ARN" \
  --output proposal.json \
  --output-cloudformation cfn-patch.yml \
  --output-terraform tf-patch.tf

# Less strict guardrails
poetry run alpha analyze --role-arn "$ROLE_ARN" --guardrails sandbox

# Exclude services
poetry run alpha analyze --role-arn "$ROLE_ARN" --exclude-services ec2,rds

# Create PR
poetry run alpha propose --repo org/repo --branch harden/role --input proposal.json

# Dry-run deployment
poetry run alpha apply --state-machine-arn "$ARN" --proposal proposal.json --dry-run
```

## Next Steps

1. **Try judge mode first** to learn the tool
2. **Analyze a non-critical role** in your account
3. **Review the proposal** before applying anything
4. **Deploy infrastructure** only if you want full automation
5. **Use `--dry-run`** on `alpha apply` until you trust it

**Don't apply policies blindly. Review the diff first.**
