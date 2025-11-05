# ALPHA - IAM Policy Auditor

Scan CloudTrail, generate least-privilege IAM policies in seconds.

## Why

Your IAM roles have `s3:*`, `dynamodb:*`, `AdminAccess` everywhere.
Security asks "why does this role need all these permissions?"
You spend 2 hours digging through CloudTrail logs to find out.

**ALPHA does it in 5 seconds.**

## Install

```bash
git clone https://github.com/YOUR_ORG/alpha.git
cd alpha
poetry install
```

## Use

```bash
# See what a role actually uses
poetry run alpha analyze \
  --role-arn arn:aws:iam::123456789012:role/YourRole \
  --usage-days 30 \
  --output policy.json

# Get Terraform/CloudFormation patches
poetry run alpha analyze \
  --role-arn arn:aws:iam::123456789012:role/YourRole \
  --output-terraform patch.tf \
  --output-cloudformation patch.yml
```

**Output shows:**
- What permissions are actually used
- What's safe to remove
- Ready-to-use Terraform/CloudFormation patches

## Common Scenarios

### "Why does this role have s3:*?"

```bash
alpha analyze --role-arn arn:aws:iam::123:role/SuspiciousRole --usage-days 90
```

Output: "Used 3 S3 actions in 90 days: GetObject, ListBucket, PutObject. Never used DeleteBucket, DeleteObject, or 2,844 other permissions."

**Answer in 5 seconds, not 2 hours.**

### "What permissions for new Lambda?"

```bash
# Deploy to staging with AdminAccess
# Let it run 24 hours
alpha analyze --role-arn arn:aws:iam::123:role/NewLambda-staging --usage-days 1
```

Output: Tight policy based on actual usage. Deploy to prod with least-privilege from day 1.

### "Did tightening IAM break production?"

```bash
alpha analyze --role-arn arn:aws:iam::123:role/BrokenRole --usage-days 0.1
```

Output: Shows what permissions were called in last 2 hours. Instantly see what's missing.

## What It Does

1. Scans CloudTrail Event History (fast, ~5 seconds)
2. Finds all API calls made by the role
3. Generates IAM policy with only those permissions
4. Applies safety guardrails
5. Outputs JSON + Terraform + CloudFormation

## Commands

### analyze

```bash
alpha analyze --role-arn <ARN> [options]
```

**Options:**
- `--usage-days N` - Days to scan (default: 30)
- `--output FILE` - Save JSON proposal
- `--output-terraform FILE` - Save Terraform patch
- `--output-cloudformation FILE` - Save CloudFormation patch
- `--guardrails {none|sandbox|prod}` - Safety level (default: prod)
- `--exclude-services SVCS` - Skip services (e.g., `ec2,rds`)
- `--suppress-actions ACTIONS` - Block specific actions

### propose

Create GitHub PR with policy changes:

```bash
export GITHUB_TOKEN=ghp_your_token
alpha propose --repo org/infra --branch alpha/harden-role --input policy.json
```

## Requirements

- Python 3.11+
- AWS credentials configured
- CloudTrail enabled

**AWS permissions needed:**
- `cloudtrail:LookupEvents`
- `iam:GetRole`, `iam:GetRolePolicy`

## Guardrails

**prod (default):**
- Blocks `iam:*`, `sts:AssumeRole`
- Requires region conditions
- Disallows `iam`, `organizations` services

**sandbox:**
- Blocks `iam:PassRole` only

**none:**
- No restrictions

## Exit Codes (for CI/CD)

- **0** - Success
- **1** - Tool error
- **3** - Guardrail violation

```yaml
# In CI pipeline
- run: alpha analyze --role-arn $ROLE_ARN --guardrails prod
  # Fails pipeline if exit code >= 3
```

## What It Doesn't Do

- ❌ Doesn't modify IAM automatically (you review and deploy)
- ❌ Doesn't add resource ARN scoping (uses `*`, you tighten manually)
- ❌ Doesn't know about future use cases (only past usage)

## Troubleshooting

**"No CloudTrail events"** - Role hasn't been used recently. Try `--usage-days 1`.

**"AWS credentials not configured"** - Run `aws configure` or set env vars.

## Cost

**Free.** CloudTrail Event History API and IAM API calls have no charge.

## When to Use ALPHA vs Alternatives

**Use ALPHA when:**
- You need fast answers (incident response, quick audits, dev workflow)
- You want Terraform/CloudFormation output ready to commit
- You prefer CLI over AWS Console
- You're checking staging roles before promoting to prod

**Use AWS Access Analyzer when:**
- You need the most comprehensive analysis (90 day deep dive)
- You want resource-scoped policies (specific ARNs, not `*`)
- You're doing quarterly compliance audits (time isn't critical)
- Official AWS tooling is required by your org

**Use iamlive when:**
- You're developing new code and need policies as you write
- You want to generate policies without CloudTrail history
- You're working in local/dev environments

**Use CloudTracker/RepoKid when:**
- You need organization-wide continuous auditing
- You want automated removal (high-risk, high-reward)
- You have complex multi-account setups

ALPHA is the **fast, practical middle ground**: quicker than Access Analyzer, more audit-focused than iamlive, simpler than enterprise tools.

## License

MIT

---

**Stop spending hours auditing IAM. Get answers in seconds.**
