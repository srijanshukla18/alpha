# ALPHA Lab Setup (record-a-demo ready)

The goal: one command on a blank AWS account that produces an over‑privileged role, deploys ALPHA’s rollout stack, and generates a proposal you can show in a recording.

## What the lab script does
- Ensures IAM Access Analyzer and a CloudTrail trail exist (creates both if missing).
- Creates a deliberately over‑privileged role `AlphaDemoOverPerm` (s3:*, dynamodb:*, logs:*).
- Deploys the ALPHA CDK stack (Lambdas, Step Functions, approvals/baseline tables, metrics).
- Installs Python deps via `uv sync` and runs `alpha analyze` against the demo role, writing:
  - `proposal.json`
  - `cfn-patch.yml`
  - `tf-patch.tf`

## Run it
```bash
export AWS_REGION=us-east-1   # or your region
./scripts/alpha_lab.sh apply
```
Outputs: a proposal ready to review plus CFN/TF patches. State machine and tables are deployed for `alpha apply` / `alpha drift` demos.
The script also generates real CloudTrail usage for the demo role by launching a tiny EC2 instance that calls S3/DynamoDB/CloudWatch Logs, then terminates.

## Clean up
```bash
./scripts/alpha_lab.sh cleanup
```

## Prereqs
- AWS CLI configured (target account)
- Node/npm + AWS CDK v2 (`npm i -g aws-cdk`), uv, aws credentials with permissions for IAM, CloudTrail, Access Analyzer, Lambda, Step Functions, DynamoDB, S3.

## Suggested demo flow
1) Show `proposal.json` risk/guardrails + IaC patches.
2) Dry-run rollout:  
   `uv run alpha apply --state-machine-arn <ARN from cdk output> --proposal proposal.json --dry-run`
3) Live apply (canary 10%):  
   `uv run alpha apply --state-machine-arn <ARN> --proposal proposal.json --environment sandbox --canary 10`
4) Drift check after manual change:  
   `BASELINE_TABLE_NAME=alpha-baselines uv run alpha drift --role-arn arn:aws:iam::<acct>:role/AlphaDemoOverPerm`
