# ALPHA Architecture

ALPHA is a CLI-first agent designed for the full lifecycle of IAM least-privilege hardening.

## Core Components

### 1. Policy Collectors
- **Fast Mode (Default):** Queries `cloudtrail:LookupEvents` to map recent activity to IAM actions. Minimal latency, best-effort scoping.
- **Analyzer Mode:** Orchestrates IAM Access Analyzer (`StartPolicyGeneration`) for resource-scoped policies based on historical trails.

### 2. Bedrock Reasoning
Uses LLMs (Claude Sonnet 4.5 or Nova Pro) to:
- Assess probability of breakage based on usage patterns.
- Provide human-readable rationale for SRE review.
- Suggest remediation steps for identified risks.
- *Fallback:* A rule-based engine provides basic safety signals if Bedrock is unavailable.

### 3. Safety Guardrails
Post-processing engine that enforces hard constraints:
- Strips wildcards from sensitive actions.
- Blocks `iam:PassRole`, `sts:AssumeRole`, and organizational management actions.
- Enforces regional restrictions and mandatory condition keys.
- Triggers non-zero exit codes (0/2/3) to gate CI/CD pipelines.

### 4. Lifecycle Orchestration
- **Drift Detection:** Compares local proposal files against live IAM role states.
- **Staged Rollout:** Triggers AWS Step Functions (via `alpha apply`) for canary deployments.
- **Rollback:** Inverts the proposal logic to restore the pre-hardening state in seconds.

## Data Flow

1. **Analyze:** Collector → Bedrock → Guardrails → Proposal JSON + IaC Patch (TF/CFN).
2. **Review:** PR creation via `alpha propose` with embedded risk metrics.
3. **Deploy:** `alpha apply` → Step Functions → Canary (10%) → Monitor → Promote (100%).
4. **Ops:** `alpha status` to monitor; `alpha diff` to check for drift; `alpha rollback` for emergencies.

## Integration Points

- **GitHub Actions:** Native composite action in `action/`.
- **Infrastructure as Code:** Generates ready-to-paste snippets for Terraform and CloudFormation.
- **AgentCore:** Entrypoint in `src/alpha_agent/agentcore_entrypoint.py` for deploying as a managed service.

## Security Controls

- **Mock Mode:** Deterministic offline execution for testing (`--mock-mode`).
- **Auditability:** All proposals include the original policy and AI rationale for a permanent audit trail.
- **Gating:** Exit code `2` (Risky) and `3` (Violation) stop pipelines by default.