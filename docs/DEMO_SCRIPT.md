# ALPHA – 3‑Minute Demo Script

Use this script to narrate and run a reliable, high‑impact demo that shows fast analysis, AI reasoning, guardrails, and a safe rollout via Step Functions.

## Prep (off‑camera)

- export ROLE_ARN=arn:aws:iam::097607620475:role/AlphaDemoRole
- export AWS_REGION=us-east-1
- Optional: export ALPHA_BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
- Optional (for rollout): export STATE_MACHINE_ARN=arn:aws:states:us-east-1:...:stateMachine:AlphaMinimalRollout

Sanity:
- aws sts get-caller-identity
- poetry run alpha --version

## Run the demo (3:00)

0:00–0:15 — Hook
- Say: “95% of IAM permissions are never used. Copy‑pasted policies ship ‘s3:*’ into prod. ALPHA fixes this in seconds — not weeks.”

0:15–0:25 — One‑liner
- Say: “ALPHA analyzes real CloudTrail activity, proposes least‑privilege with Bedrock reasoning, enforces guardrails, and can roll out safely via Step Functions.”

0:25–1:25 — Analyze (fast, real AWS)
- Run:
```
poetry run alpha analyze \
  --role-arn "$ROLE_ARN" \
  --usage-days 1 \
  --guardrails sandbox \
  --output proposal.json \
  --output-cloudformation cfn.yml \
  --output-terraform tf.tf
```
- Say while running: “Fast mode is default — no Access Analyzer job — so it completes in seconds using CloudTrail Event History.”
- Inspect:
```
ls -lh proposal.json cfn.yml tf.tf
```
- Explain: “We get rationale, a risk score, and ready‑to‑paste CloudFormation and Terraform patches.”

1:25–1:45 — Guardrails prove safety
- Run:
```
poetry run alpha analyze \
  --role-arn "$ROLE_ARN" \
  --usage-days 1 \
  --guardrails prod \
  --output /tmp/ignore.json
```
- Say: “In prod preset, guardrails block risky services and wildcards — exit code 3 shows it.”

1:45–2:25 — Staged rollout (Step Functions)
- Dry‑run:
```
poetry run alpha apply \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --proposal proposal.json \
  --dry-run
```
- Say: “Rollouts are stage‑gated. This is the exact payload our state machine receives.”
- Live:
```
poetry run alpha apply \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --proposal proposal.json
```
- Say: “We default approvals off for demos; one flag adds DynamoDB approvals. Console link prints here.”

2:25–2:45 — CI/CD story
- Say: “Exit codes: 0 safe, 1 tool error, 2 risky (>10%), 3 guardrail violation — pipelines block unsafe changes automatically.”

2:45–3:00 — Close
- Say: “In under a minute of runtime, we produced an explainable least‑privilege policy from real usage, enforced guardrails, and kicked off a safe rollout. Practical today; Analyzer path available when you want deeper scoping.”

## Contingencies
- No Bedrock access → ALPHA falls back and still emits outputs; mention “graceful fallback.”
- No CloudTrail events → try `--usage-days 7` or judge mode:
```
poetry run alpha analyze --role-arn arn:aws:iam::123456789012:role/TestRole --judge-mode --output proposal.json
```
- Analyzer mention (optional): `--no-fast` with `--timeout-seconds` for Access Analyzer.
