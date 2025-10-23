# ALPHA – Autonomous Least-Privilege Hardening Agent

![AWS AI Agent Global Hackathon](https://img.shields.io/badge/AWS-AI_Agent_Hackathon-FF9900?style=for-the-badge&logo=amazon-aws)
![Python](https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python)
![License](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)

ALPHA is an AWS‑native AI agent that right‑sizes IAM policies from real usage. It supports two analysis paths:
- ⚡ Fast Mode (default): uses CloudTrail Event History for a best‑effort policy in seconds (no Access Analyzer job)
- ☁️ Analyzer Mode (optional): uses IAM Access Analyzer for resource‑scoped policies (slower)

Bedrock reasoning (Anthropic Claude or Amazon Nova Pro) provides rationale and risk; guardrails enforce hard constraints. CLI‑first, CI‑friendly.

## 30‑Second Quickstart (fast mode by default)

```bash
poetry install
poetry run alpha analyze \
  --role-arn arn:aws:iam::123456789012:role/YourRole \
  --guardrails sandbox \
  --output proposal.json \
  --output-cloudformation cfn-patch.yml \
  --output-terraform tf-patch.tf
```

Notes
- Fast mode is on by default. Use `--no-fast` to force Access Analyzer.
- To use Nova Pro: set `ALPHA_BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0`.
- No Bedrock access? ALPHA falls back and still produces outputs.

## Problem

- 95% of IAM permissions never used in production
- Roles have `AdminAccess` or `*` wildcards
- Manual policy audits take weeks
- Fear of breaking prod prevents fixes

## Solution

**Three commands. Full automation.**

### 1. `alpha analyze` - Generate Policy
```bash
alpha analyze \
  --role-arn arn:aws:iam::YOUR_ACCOUNT:role/YourRole \
  --output proposal.json \
  --output-cloudformation cfn-patch.yml \
  --output-terraform tf-patch.tf \
  --guardrails prod
```

Behind the scenes
- Fast: CloudTrail Event History → best‑effort actions (Resource "*")
- Analyzer: Access Analyzer → resource‑scoped actions from trails
- Bedrock (Claude or Nova) adds rationale/risk; guardrails enforce org rules

Exit codes: 0=safe, 1=error, 2=risky (>10%), 3=guardrail violation

### 2. `alpha propose` - Create PR
```bash
export GITHUB_TOKEN=ghp_your_token
alpha propose --repo org/infra --branch harden/role --input proposal.json
```

Auto-generates PR with:
- Risk assessment + confidence score
- Before/after policy diff
- Privilege reduction metrics (e.g., "85% reduction: 2,847 → 5 actions")

### 3. `alpha apply` - Staged Rollout
```bash
alpha apply \
  --state-machine-arn arn:aws:states:us-east-1:123:stateMachine/Alpha \
  --proposal proposal.json \
  --environment prod \
  --canary 10
```

**Step Functions workflow:**
1. Validate policy + check approval (DynamoDB)
2. Canary deploy (10% traffic)
3. Monitor CloudWatch (watch for AccessDenied spikes)
4. Auto-rollback if errors > 0.1%, else promote to 100%

## Key Features

- CLI‑first with CI exit codes (0/1/2/3)
- Fast mode default; Analyzer optional
- Bedrock reasoning (Claude or Nova Pro) with graceful fallback
- Guardrails presets (none/sandbox/prod) + custom excludes/suppression
- Multi‑format outputs: JSON, CloudFormation YAML, Terraform HCL, PR markdown
- Judge Mode for offline demos (deterministic)

## Installation

```bash
# Poetry (recommended)
git clone https://github.com/your-org/alpha.git && cd alpha && poetry install

# pipx (when published to PyPI)
pipx install alpha-agent
```

## CLI Reference

### `analyze` Options
```bash
--role-arn              # IAM role ARN (required)
--usage-days 30         # CloudTrail analysis window
--output proposal.json  # Save proposal JSON
--output-cloudformation cfn.yml  # CloudFormation patch
--output-terraform tf.tf         # Terraform patch
--guardrails prod       # none/sandbox/prod
--exclude-services ec2,rds       # Skip services
--suppress-actions s3:DeleteBucket  # Block specific actions
--baseline-policy-name Current   # Diff against existing policy
--judge-mode            # Offline mock mode (no AWS)
--no-fast               # Use Access Analyzer instead of fast mode
--timeout-seconds 1800  # Wait budget for Access Analyzer path
--bedrock-model us.amazon.nova-pro-v1:0  # Override Bedrock model
```

### `propose` Options
```bash
--repo org/infra        # GitHub repository
--branch harden/role    # Branch name
--input proposal.json   # Proposal from analyze
--base main             # Base branch
--title "Custom title"  # Override auto-generated title
--draft                 # Create as draft PR
--github-token ghp_xxx  # Or set GITHUB_TOKEN env
```

### `apply` Options
```bash
--state-machine-arn arn:...  # Step Functions ARN
--proposal proposal.json     # Proposal file
--environment prod           # sandbox/canary/prod
--canary 10                  # Canary percentage
--rollback-threshold "AccessDenied>0.1%"
--require-approval           # Check DynamoDB approval
--approval-table Approvals   # DynamoDB table name
--dry-run                    # Simulate without executing
--judge-mode                 # Mock execution
```

## Guardrails

none: no restrictions (sandbox)
sandbox: blocks `iam:PassRole`
prod: blocks `iam:*`, `sts:AssumeRole`; requires `StringEquals: { aws:RequestedRegion: us-east-1 }`; disallows `iam`, `organizations`

Custom:
```bash
--exclude-services ec2,lambda --suppress-actions dynamodb:DeleteTable
```

Violations trigger exit code 3 and block deployment.

## GitHub Action

```yaml
- uses: your-org/alpha@v1
  with:
    mode: analyze
    role_arn: arn:aws:iam::123:role/MyRole
    guardrails: prod
    output_path: proposal.json

- name: Block risky changes
  if: steps.analyze.outputs.exit_code >= 2
  run: exit 1
```

See `.github/workflows/` for complete examples (analyze on PR, apply on merge).

## Architecture (high‑level)

- Fast collector: CloudTrail Event History → best‑effort action set
- Analyzer collector (optional): Access Analyzer → resource‑scoped actions from trails
- Reasoning: Bedrock (Claude or Nova) → rationale, risk, notes
- Guardrails: enforce org constraints; gate CI with exit codes
- Outputs: JSON, CFN, TF; optional PR creation; optional staged rollout via Step Functions

## Examples

```bash
# Try offline with judge mode
alpha analyze --role-arn arn:aws:iam::123:role/OverprivilegedAdmin --judge-mode

# Real AWS analysis with all outputs
alpha analyze \
  --role-arn arn:aws:iam::YOUR_ACCOUNT:role/YourRole \
  --output proposal.json \
  --output-cloudformation cfn-patch.yml \
  --output-terraform tf-patch.tf

# Full workflow
alpha analyze --role-arn <ARN> --output proposal.json
alpha propose --repo org/repo --branch harden/role --input proposal.json
alpha apply --state-machine-arn <ARN> --proposal proposal.json --dry-run
```

Sample inputs in `examples/inputs/` (admin role, CI runner, data pipeline).

## Testing

```bash
./test_judge_mode.sh  # End-to-end validation (no AWS creds needed)
```

Validates all commands, guardrails, outputs, and judge mode determinism.

## Deployment (optional)

CDK stack under `infra/` provisions the staged rollout system (Step Functions, Lambdas, DynamoDB, CloudWatch). For analyzer mode, also provision an Access Analyzer and CloudTrail trails. See ARCHITECTURE.md for details.

### Minimal Step Functions workflow (quick demo)

```bash
# create an IAM role for Step Functions if you don't already have one
# (trust states.amazonaws.com; attach AmazonStepFunctionsFullAccess for quick demos)
aws iam create-role \
  --role-name AlphaStepFunctionsRole \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"states.amazonaws.com"},"Action":"sts:AssumeRole"}]}' || true

aws iam attach-role-policy \
  --role-name AlphaStepFunctionsRole \
  --policy-arn arn:aws:iam::aws:policy/AWSStepFunctionsFullAccess || true

export SFN_ROLE_ARN=arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/AlphaStepFunctionsRole

# create a minimal state machine (all Pass states)
aws stepfunctions create-state-machine \
  --name AlphaMinimalRollout \
  --definition file://workflows/minimal_state_machine.asl.json \
  --role-arn "$SFN_ROLE_ARN"

# capture the ARN that is returned and use it with alpha apply
export STATE_MACHINE_ARN=arn:aws:states:us-east-1:...:stateMachine:AlphaMinimalRollout

poetry run alpha apply \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --proposal proposal.json \
  --dry-run
```

Real runs default to `--require-approval False`; pass `--require-approval --approval-table <table>` to enforce approvals.

### AgentCore Runtime (optional)

You can deploy ALPHA primitives as managed AgentCore Runtime endpoints:

Entrypoint module: `src/alpha_agent/agentcore_entrypoint.py`

Single entrypoint with action dispatch:
- `action: "enforce_policy_guardrails"` → returns `sanitized_policy` + `violations`
- `action: "analyze_fast_policy"` → returns best‑effort policy from CloudTrail Event History

Quick deploy (using AgentCore Starter Toolkit):

```bash
# 0) One-time project bootstrap (recommended)
./scripts/bootstrap_agentcore.sh agentcore_deploy

# 1) Configure and launch (from repo root, using the project directory)
uv --directory agentcore_deploy run agentcore configure -e src/alpha_agent/agentcore_entrypoint.py
uv --directory agentcore_deploy run agentcore launch
uv --directory agentcore_deploy run agentcore status

# 2) Invoke examples (from repo root)
uv --directory agentcore_deploy run agentcore invoke '{"action":"analyze_fast_policy","roleArn":"'$ROLE_ARN'","usageDays":1,"region":"'$AWS_REGION'"}'
uv --directory agentcore_deploy run agentcore invoke '{"action":"enforce_policy_guardrails","policy":{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"s3:*","Resource":"*"}]},"preset":"prod"}'
```

## Repository Structure

```
alpha/
├── src/alpha_agent/
│   ├── cli/              # CLI commands (analyze, propose, apply)
│   │   ├── formatters.py # JSON, CFN, TF, PR, terminal outputs
│   │   └── judge_mode.py # Mock data for offline demos
│   ├── main.py           # CLI entrypoint
│   ├── reasoning.py      # Bedrock reasoning (Claude or Nova)
│   ├── collector.py      # Access Analyzer collector (optional)
│   ├── fast_collector.py # Fast CloudTrail Event History collector (default)
│   ├── guardrails.py     # Security constraints
│   ├── diff.py           # Policy diffing
│   └── models.py         # Pydantic schemas
├── action/action.yml     # GitHub Action composite
├── .github/workflows/    # Example workflows
├── examples/             # Sample inputs/outputs
├── lambdas/              # Lambda handlers
├── infra/                # CDK infrastructure
├── workflows/            # Step Functions definitions (minimal demo, legacy)
└── test_judge_mode.sh    # E2E test script
```

## Demo & Hackathon

Judge Mode enables fully offline demos. For a live demo, prefer fast mode to avoid Access Analyzer latency. For hackathon submission text, see `hackathon.md` (rules) and `idea.md` (concept). 

Run the guided demo:

```bash
python3 demo_repl.py --role-arn "$ROLE_ARN" --state-machine-arn "$STATE_MACHINE_ARN"
```

**Built for:** AWS AI Agent Global Hackathon 2025
**Category:** Best Bedrock AgentCore Implementation

**Why ALPHA wins:**
1. **Production-ready** - Not a toy, ships as CLI + GitHub Action
2. **Judge Mode** - Offline deterministic demos without AWS
3. **Bedrock reasoning** - Claude Sonnet 4.5 adds edge-case permissions, assesses risk
4. **Real AWS integration** - Access Analyzer (CloudTrail analysis) + Step Functions (staged rollout)
5. **Multi-format outputs** - CFN, TF patches ready to paste into IaC
6. **Guardrails** - Hard constraints (can't be bypassed by LLM)
7. **Comprehensive** - CLI, Action, infra, docs, tests

Use this README, QUICKSTART.md, and docs/ARCHITECTURE.md for submission content.

### AgentCore (optional)

- Tools exposed in `src/alpha_agent/agentcore.py`: generate policy, reason, enforce guardrails, diff, approvals, rollout, GitHub PR
- Register with Amazon Bedrock AgentCore Gateway using `get_agentcore_tool_definitions()`
- Handler Lambda at `lambdas/agentcore_runtime/handler.py` wires the tools; prompts can be defined dynamically (see code)
- Great for the “agentic” judging track; CLI remains the primary interface

## License

MIT

---

**Stop copying IAM policies from Stack Overflow. Let AI do the work.**
Built with ❤️ for AWS AI Agent Global Hackathon • [GitHub](https://github.com/your-org/alpha) • [Demo Video](#)
