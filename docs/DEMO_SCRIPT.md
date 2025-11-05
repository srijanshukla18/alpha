# ALPHA – 3‑Minute Demo Script

Use this script with demo_repl.py to narrate a reliable 3‑minute demo that shows fast analysis, guardrails, Step Functions rollout, and AgentCore Runtime. The REPL pauses at each step so you can talk while pressing Enter to advance (or 's' to skip).

## Prep (off‑camera)

- export ROLE_ARN=arn:aws:iam::123456789012:role/AlphaDemoRole
- export AWS_REGION=us-east-1
- Optional: export ALPHA_BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
- Optional (for rollout): export STATE_MACHINE_ARN=arn:aws:states:us-east-1:...:stateMachine:AlphaMinimalRollout
- Optional (AgentCore): Deploy once off‑camera (takes a minute) so we only run status/invoke on‑camera:
  - uv run agentcore configure -e src/alpha_agent/agentcore_entrypoint.py
  - uv run agentcore launch

Sanity:
- aws sts get-caller-identity
- poetry run alpha --version

## Run the demo (3:00) with the REPL

Start the REPL:
```
python3 demo_repl.py --role-arn "$ROLE_ARN" --state-machine-arn "$STATE_MACHINE_ARN"
```

0:00–0:15 — Hook
- Say: “95% of IAM permissions are never used. Copy‑pasted policies ship ‘s3:*’ into prod. ALPHA fixes this in seconds — not weeks.”

0:15–0:25 — One‑liner
- Say: “ALPHA analyzes real CloudTrail activity, proposes least‑privilege with Bedrock reasoning, enforces guardrails, and can roll out safely via Step Functions.”

0:25–1:20 — REPL Step: Analyze (fast, real AWS)
- Press Enter to run analyze
- Say while it runs: “Fast mode is default — no Access Analyzer job — so it completes in seconds using CloudTrail Event History.”
- When outputs list appears, say: “We get rationale, a risk score, and ready‑to‑paste CloudFormation and Terraform patches.”

1:20–1:40 — REPL Step: Guardrails (prod)
- Press Enter to run prod guardrails check
- Say: “In prod preset, guardrails block risky services and wildcards — the REPL prints a non‑zero exit code.”

1:40–2:10 — REPL Steps: Step Functions (dry‑run → live)
- Dry‑run: Press Enter to show the execution payload
- Say: “This is the payload our state machine receives.”
- Live: Press Enter to start a real execution (Pass‑only workflow finishes instantly)
- Say: “Approvals off by default for demo; one flag adds DynamoDB approvals. Console link prints here.”

2:25–2:45 — CI/CD story
- Say: “Exit codes: 0 safe, 1 tool error, 2 risky (>10%), 3 guardrail violation — pipelines block unsafe changes automatically.”

2:45–3:00 — Close
- Say: “In under a minute of runtime, we produced an explainable least‑privilege policy from real usage, enforced guardrails, and kicked off a safe rollout. Practical today; Analyzer path available when you want deeper scoping.”

## Contingencies (keep moving if these trigger)
- No Bedrock access → ALPHA falls back and still emits outputs; mention “graceful fallback.”
- No CloudTrail events → try `--usage-days 7` or judge mode:
```
poetry run alpha analyze --role-arn arn:aws:iam::123456789012:role/TestRole --judge-mode --output proposal.json
```
- Analyzer mention (optional): `--no-fast` with `--timeout-seconds` for Access Analyzer.

## AgentCore Runtime (on‑camera, ~40s)

- Pre‑deploy off‑camera (configure + launch). On‑camera we do status and two quick invocations via the REPL.
- Narration:
  - “These primitives are deployed as managed endpoints (single entrypoint with an action).”
  - “We’ll call analyze_fast_policy and enforce_policy_guardrails.”
- In the REPL:
  - Press Enter for `agentcore status`
  - Press Enter to invoke `analyze_fast_policy` (fast)
  - Press Enter to invoke `enforce_policy_guardrails` on a toy wildcard policy (shows violations)
