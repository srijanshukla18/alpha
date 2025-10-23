# ALPHA Architecture (Condensed)

This document reflects the current implementation (fast mode default, Analyzer optional, Bedrock model override).

## High‑Level

- Fast collector (default): CloudTrail Event History → best‑effort actions (Resource "*")
- Analyzer collector (optional): IAM Access Analyzer → resource‑scoped actions from trails
- Reasoning: Bedrock (Claude or Nova Pro), provider‑aware payloads with graceful fallback
- Guardrails: post‑processing constraints; CI exit codes for gating
- Outputs: JSON, CFN, TF; optional PR and staged rollout

## Analyze Flow

1) Collect
   - Fast: `cloudtrail:LookupEvents`; map `eventSource + eventName` → `service:Action`; group by service
   - Analyzer: `StartPolicyGeneration`; poll `GetGeneratedPolicy`
2) Reason
   - Bedrock returns rationale, risk, remediation notes (Anthropic/Nova)
   - Fallback used if Bedrock not enabled/available
3) Guardrails
   - Remove wildcards; block `iam:PassRole` (sandbox) or `iam:*`, `sts:AssumeRole` (prod); enforce region condition; disallow `iam`, `organizations`
4) Output
   - Terminal summary, JSON bundle, CFN/TF patches; optional PR

## Orchestration (optional)

- Minimal workflow: `workflows/minimal_state_machine.asl.json` (all Pass states) for quick demos
- Production workflow: CDK app under `infra/` (Step Functions + Lambdas + DynamoDB + CloudWatch)
- `alpha apply` default payload fields: `roleArn`, `environment`, `canaryPercent`, `rollbackThreshold`, `proposal`, `metadata`

## Permissions

- Fast: `cloudtrail:LookupEvents`, `iam:GetRole*`, `bedrock:InvokeModel`
- Analyzer: add `access-analyzer:StartPolicyGeneration`, `access-analyzer:GetGeneratedPolicy`
- Rollout: `states:StartExecution`, `iam:PutRolePolicy/GetRolePolicy`

## Bedrock Models

- Default: Anthropic Sonnet 4.5 (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`)
- Nova option: `us.amazon.nova-pro-v1:0`
- Override via `--bedrock-model` or `ALPHA_BEDROCK_MODEL_ID`
- If the model isn’t enabled, ALPHA falls back and still emits outputs

## Data Models

PolicyDocument, PolicyProposal, PolicyDiff are defined in `src/alpha_agent/models.py` using Pydantic v2.

Example PolicyDocument
```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*" }
  ]
}
```

## Security

- Guardrails run after reasoning and can strip risky suggestions
- Exit codes enable CI gating (0/1/2/3)
- Judge Mode supports deterministic offline demos

## Deployment

- CLI only (default) – no infra required
- Orchestrated rollout – deploy CDK in `infra/` (Step Functions, Lambdas, DynamoDB, CloudWatch)

## AgentCore (optional)

- Entrypoint for Runtime: `src/alpha_agent/agentcore_entrypoint.py`
  - `enforce_policy_guardrails(payload)` → sanitized policy + violations
  - `analyze_fast_policy(payload)` → best‑effort policy via CloudTrail Event History
- Tools library (optional): `src/alpha_agent/agentcore.py` defines AgentCoreTools for broader orchestration
- Hosted handler (optional): `lambdas/agentcore_runtime/handler.py` for managed tool orchestration
- Use Runtime entrypoint to deploy minimal, production‑friendly endpoints quickly

## Repo Pointers

- CLI entry: `src/alpha_agent/main.py`
- Analyze: `src/alpha_agent/cli/analyze.py`
- Fast collector: `src/alpha_agent/fast_collector.py`
- Analyzer collector: `src/alpha_agent/collector.py`
- Reasoning: `src/alpha_agent/reasoning.py`
- Guardrails: `src/alpha_agent/guardrails.py`
- Formatters: `src/alpha_agent/cli/formatters.py`
