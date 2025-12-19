# ALPHA – The "Undo" Button for IAM

**Autonomous Least-Privilege with a Safety Net.**

ALPHA is a production-grade agent that rightsizes IAM policies based on real usage telemetry. It turns the "fear of breaking production" into a non-issue with AI-powered risk signals, staged rollouts, and instant emergency recovery.

## Why SREs use ALPHA:

1.  **Prioritized Hardening:** `alpha audit` scans your account and tells you exactly which roles are the most over-privileged.
2.  **Explainable Risk:** Bedrock-powered reasoning tells you *why* it's safe to remove a permission and what the blast radius is.
3.  **Staged Rollouts:** Deploy via Step Functions with canary traffic and auto-rollback on `AccessDenied` spikes.
4.  **Instant Recovery:** Hit the "Undo" button with `alpha rollback` to restore pre-hardening state in seconds.

---

## 30-Second Quickstart

```bash
# 1. Install
pip install alpha-agent  # or poetry install

# 2. Find where the risk is
alpha audit --limit 5

# 3. Harden a role
alpha analyze --role-arn arn:aws:iam::123:role/Overprivileged --output proposal.json
```

---

## The Hardening Lifecycle

### 1. `analyze` → Human-Readable Rationale
Generates least-privilege policies using CloudTrail + Bedrock risk assessment.
```bash
alpha analyze --role-arn $ROLE --output proposal.json
```
*Outputs:* JSON bundle, Rationale, and ready-to-paste **Terraform/CloudFormation** patches.

### 2. `propose` → Peer Reviewed PRs
Creates a GitHub PR with metrics like "**85% Privilege Reduction**".
```bash
alpha propose --repo org/infra --branch harden/role --input proposal.json
```

### 3. `apply` → Zero-Downtime Rollout
Triggers a Step Functions workflow with canary deployment and automated health checks.
```bash
alpha apply --state-machine-arn $SFN_ARN --proposal proposal.json --canary 10
```

---

## Day 2 Operations (The SRE Toolkit)

| Command | Action | Value |
| :--- | :--- | :--- |
| `audit` | Scan account roles | Identify the top 10 biggest privilege gaps. |
| `diff` | Compare against live | Detect manual "permission creep" instantly. |
| `status` | Track rollout | Monitor canary progress from your terminal. |
| `rollback` | Emergency revert | Instant "Undo" (even without the proposal file). |

---

## Installation & Setup

```bash
git clone https://github.com/your-org/alpha.git && cd alpha && poetry install
```

**Mock Mode (Zero-Cost Testing):**
Test your CI pipelines without AWS credentials or Bedrock costs:
```bash
alpha audit --mock-mode
alpha analyze --role-arn arn:aws:iam::123:role/MockRole --mock-mode
```

[Quickstart Guide](QUICKSTART.md) • [Architecture](docs/ARCHITECTURE.md)

---
Built for Production Stability • Best-in-class Bedrock Implementation