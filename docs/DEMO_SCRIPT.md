# Operational Walkthrough (SRE Guide)

Use this guide to demonstrate the full lifecycle of ALPHA in a production-like environment. 

## Prerequisites

- `export ROLE_ARN=arn:aws:iam::ACCOUNT_ID:role/TargetRole`
- `export SFN_ARN=arn:aws:states:REGION:ACCOUNT_ID:stateMachine:AlphaRollout`
- `poetry install`

---

## Phase 1: High-Confidence Hardening

### 1. Analyze with Bedrock Rationale
Demonstrate how ALPHA generates a policy and explains its reasoning.
```bash
alpha analyze --role-arn "$ROLE_ARN" --output proposal.json
```
*Key points to mention:*
- **Fast Mode:** Finishes in seconds using CloudTrail Event History.
- **Rationale:** AI explains why certain permissions are kept vs. removed.
- **Risk Signal:** Quantitative probability of causing a production outage.

### 2. Peer Review Integration
Show how ALPHA generates IaC patches and PR content.
```bash
cat proposal.json | jq '.proposal.proposed_policy'
# Or check the generated cfn/tf files if --output-terraform was used.
```

---

## Phase 2: Safe Staged Rollout

### 3. Dry-Run & Approval Check
Verify the deployment payload before triggering the Step Function.
```bash
alpha apply --state-machine-arn "$SFN_ARN" --proposal proposal.json --dry-run
```

### 4. Live Staged Deployment
Trigger the canary rollout (10% traffic).
```bash
alpha apply --state-machine-arn "$SFN_ARN" --proposal proposal.json --canary 10
```
*Key points to mention:*
- **Step Functions:** Orchestrates the validation, canary, and promotion stages.
- **Monitoring:** The state machine watches for `AccessDenied` spikes during the canary window.

---

## Phase 3: Day 2 Operations

### 5. Monitoring Status
Check the progress of the rollout without leaving the terminal.
```bash
alpha status --role-arn "$ROLE_ARN" --state-machine-arn "$SFN_ARN"
```

### 6. Drift Detection (The SRE Secret Weapon)
Show how to detect if a role has been manually over-privileged since the last ALPHA run.
```bash
# Simulate drift by manually adding a policy to the role, then run:
alpha diff --input proposal.json
```

### 7. Emergency Rollback
Demonstrate the "Undo" button for IAM.
```bash
alpha rollback --proposal proposal.json --state-machine-arn "$SFN_ARN"
```

---

## Testing & Development

### Mock Mode (No AWS/Bedrock Required)
Show how developers can test their CI pipelines locally without AWS credentials.
```bash
alpha analyze --role-arn arn:aws:iam::123:role/MockRole --mock-mode
```