# ALPHA – Autonomous Least-Privilege Hardening Agent

![AWS AI Agent Global Hackathon](https://img.shields.io/badge/AWS-AI_Agent_Hackathon-FF9900?style=for-the-badge&logo=amazon-aws)
![Python](https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python)

**Stop fear-based IAM management.** ALPHA is an AI agent that right-sizes IAM policies from real usage with a built-in safety net. It doesn't just generate policies; it manages their entire lifecycle.

## Why ALPHA?

1.  **High-Confidence Hardening:** Bedrock-powered reasoning explains *why* it's safe to remove a permission, reducing the fear of breaking production.
2.  **Day 2 Observability:** Built-in drift detection (`diff`) and rollout monitoring (`status`) ensure your roles stay lean.
3.  **Emergency Recovery:** One-command `rollback` reverts any change in seconds, minimizing MTTR.
4.  **Staged Rollouts:** Deploy via Step Functions with canary traffic and auto-rollback on `AccessDenied` spikes.

## 30-Second Quickstart

```bash
# Analyze a role and get IaC patches (CFN/TF) in seconds
alpha analyze --role-arn arn:aws:iam::123:role/MyRole --output proposal.json
```

## Core Workflow

### 1. `analyze` → High-Confidence Policy
Generates a least-privilege policy using CloudTrail usage + Bedrock risk assessment.
```bash
alpha analyze --role-arn $ROLE_ARN --guardrails prod --output proposal.json
```
*Exit codes: 0=safe, 2=risky (>10% break prob), 3=guardrail violation.*

### 2. `propose` → Peer Reviewed PRs
Creates a GitHub PR with metrics like "**85% Privilege Reduction**" and a full rationale.
```bash
alpha propose --repo org/infra --branch harden/role --input proposal.json
```

### 3. `apply` → Safe Staged Rollout
Triggers a Step Functions workflow with canary deployment (e.g., 10% traffic).
```bash
alpha apply --state-machine-arn $SFN_ARN --proposal proposal.json --canary 10
```

---

## Day 2 Operations (SRE Toolkit)

### 🔍 Drift Detection
Detect manual "permission creep" since the last hardening.
```bash
alpha diff --input proposal.json
```

### 📊 Rollout Monitoring
Check progress of ongoing deployments directly from the CLI.
```bash
alpha status --role-arn $ROLE_ARN --state-machine-arn $SFN_ARN
```

### 🚑 Emergency Rollback
Instant revert to the pre-ALPHA state if an edge case is hit.
```bash
alpha rollback --proposal proposal.json --state-machine-arn $SFN_ARN
```

---

## Installation & Setup

```bash
git clone https://github.com/your-org/alpha.git && cd alpha && poetry install
```

**Judge Mode (Offline Demo):**
Try it without AWS credentials:
```bash
alpha analyze --role-arn arn:aws:iam::123:role/Admin --judge-mode
```

## Key Features
- **Fast Mode (Default):** Instant results using CloudTrail Event History.
- **Analyzer Mode:** Resource-scoped policies using IAM Access Analyzer.
- **Guardrails:** Hard constraints (e.g., block `iam:*`) that can't be bypassed by AI.
- **Multi-Format:** CFN, Terraform, and JSON outputs ready for your IaC.

[Quickstart Guide](QUICKSTART.md) • [Architecture](docs/ARCHITECTURE.md) • [Hackathon Details](hackathon.md)

---
Built for **AWS AI Agent Global Hackathon 2025** • Best Bedrock AgentCore Implementation