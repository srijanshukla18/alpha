# Testing ALPHA

Three test scripts to validate ALPHA works with your AWS account.

## Quick Start

```bash
# 1. Smoke test (no AWS needed)
./test-smoke.sh

# 2. Test against existing IAM role
./test-alpha.sh

# 3. Full end-to-end test (creates test Lambda)
./test-with-lambda.sh
```

---

## Test 1: Smoke Test (No AWS)

**What it does:** Verifies ALPHA CLI is installed and working

**Run:**
```bash
./test-smoke.sh
```

**Requirements:** None (doesn't call AWS)

**Time:** 5 seconds

---

## Test 2: Quick Test (Existing Role)

**What it does:**
1. Lists IAM roles in your account
2. Lets you pick one (or uses first available)
3. Analyzes it with ALPHA
4. Shows outputs (JSON, Terraform, CloudFormation)

**Run:**
```bash
./test-alpha.sh
```

**Requirements:**
- AWS credentials configured (`aws configure`)
- At least one IAM role in your account

**Permissions needed:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:ListRoles",
        "iam:GetRole",
        "iam:GetRolePolicy",
        "cloudtrail:LookupEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

**Time:** 10-15 seconds

**Safety:** READ-ONLY. Doesn't modify anything.

---

## Test 3: End-to-End Test (Creates Lambda)

**What it does:**
1. Creates IAM role with `AdministratorAccess` (intentionally over-privileged)
2. Creates Lambda function that only uses S3 + CloudWatch
3. Invokes Lambda 3 times to generate CloudTrail events
4. Runs ALPHA to show it correctly identifies only S3/Logs are needed
5. Cleans up test resources

**Run:**
```bash
./test-with-lambda.sh
```

**Requirements:**
- AWS credentials with permissions to create Lambda + IAM roles
- CloudTrail enabled (typically on by default)

**Permissions needed:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "lambda:CreateFunction",
        "lambda:DeleteFunction",
        "lambda:InvokeFunction",
        "cloudtrail:LookupEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

**Time:** 2-3 minutes

**Safety:** Creates temporary resources, offers to clean them up at the end

**Note:** CloudTrail has 5-15 minute delay. If no events found, wait and re-run the analysis.

---

## Example Outputs

### test-alpha.sh

```bash
$ ./test-alpha.sh

==========================================
ALPHA - Quick Test Script
==========================================

1. Checking prerequisites...
2. Verifying AWS credentials...
✓ Connected to AWS account: 123456789012

3. Fetching IAM roles in your account...
Found 47 roles (excluding AWS service-linked roles)

Common roles to test:
  - ProductionAPIRole
  - DataProcessorRole
  - LambdaExecutionRole
  ...

==========================================
Select a role to analyze (or press Enter to skip)
==========================================
Role name: ProductionAPIRole

==========================================
Running ALPHA Analysis
==========================================
Role: arn:aws:iam::123456789012:role/ProductionAPIRole
Time window: 30 days

⚡ Analyzing (this takes ~5 seconds)...

==========================================
✓ Analysis Complete!
==========================================

Output files created in: ./test-output/
  - proposal.json (full analysis)
  - policy.tf (Terraform)
  - policy.yml (CloudFormation)

Quick Summary:

Rationale:
Policy based on 30 days of CloudTrail activity. Contains only observed actions.

Policy Changes:
+8 actions, -2839 actions

Guardrail Violations:
  ✓ None

View full proposal:
  cat ./test-output/proposal.json | jq

==========================================
Test Complete
==========================================

Note: This was READ-ONLY. No IAM policies were modified.
```

---

## Troubleshooting

### "AWS credentials not configured"

```bash
aws configure
# OR
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
```

### "No CloudTrail events found"

**Cause:** Role hasn't been used recently, or CloudTrail hasn't processed events yet.

**Solutions:**
- Wait 5-15 minutes (CloudTrail delay)
- Try a different role that's been used recently
- Use `--usage-days 90` for longer lookback

### "Permission denied"

**Cause:** Your AWS credentials don't have required permissions.

**Solution:** Use an IAM user/role with the permissions listed above, or:
```bash
aws iam attach-user-policy \
  --user-name YourUser \
  --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess
```

### Test Lambda not showing results

**Cause:** CloudTrail typically has 5-15 minute delay.

**Solution:** Wait a bit, then re-run analysis:
```bash
poetry run alpha analyze \
  --role-arn arn:aws:iam::123456789012:role/AlphaTestRole-... \
  --usage-days 1
```

---

## What to Expect

**Good results:**
- ALPHA finds actions the role actually used
- Generated policy is much smaller than current policy
- Terraform/CloudFormation output is ready to use

**Expected limitations:**
- Uses `Resource: "*"` (you tighten manually if needed)
- Won't catch permissions needed for disaster recovery (not in recent usage)
- CloudTrail delay means very recent activity might not show up

---

## After Testing

Once you've validated ALPHA works:

1. **Use it for real audits:**
   ```bash
   poetry run alpha analyze --role-arn <your-role> --output audit.json
   ```

2. **Integrate in CI/CD:**
   ```yaml
   - run: poetry run alpha analyze --role-arn $ROLE_ARN --guardrails prod
   ```

3. **Batch analyze all roles:**
   ```bash
   for role in $(aws iam list-roles --query 'Roles[].RoleName' --output text); do
     poetry run alpha analyze --role-arn arn:aws:iam::123:role/$role
   done
   ```
