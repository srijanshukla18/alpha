from __future__ import annotations

"""
AgentCore Runtime entrypoints for ALPHA primitives.

Provides minimal, production-friendly endpoints that can be deployed to
Amazon Bedrock AgentCore Runtime. These allow you to host ALPHA's core
capabilities as managed tools with automatic scaling and observability.

Endpoints exposed (names match function names):
  - enforce_policy_guardrails(payload, context)
      Input payload:
        {
          "policy": { ... IAM policy document ... },
          "preset": "none" | "sandbox" | "prod" (optional, default: "sandbox"),
          "extras": {
            "blocked_actions": [ ... ],
            "required_conditions": { ... },
            "disallowed_services": [ ... ]
          }
        }
      Output:
        {
          "sanitized_policy": { ... },
          "violations": [ {"code": ..., "message": ..., "path": ...}, ... ]
        }

  - analyze_fast_policy(payload, context)
      Input payload:
        { "roleArn": "arn:aws:iam::...:role/...", "usageDays": 7, "region": "us-east-1" }
      Output:
        { "policy": { ... IAM policy document ... } }

To deploy: point AgentCore Starter Toolkit to this module path as the entrypoint.
"""

import os
from typing import Any, Dict

try:
    # Provided by Amazon Bedrock AgentCore Runtime
    from bedrock_agentcore.runtime import BedrockAgentCoreApp  # type: ignore
except Exception:  # pragma: no cover - optional import for local development
    class BedrockAgentCoreApp:  # minimal shim so this module can import locally
        def entrypoint(self, fn):
            return fn

        def run(self):
            raise RuntimeError(
                "Bedrock AgentCore Runtime not available. Deploy this module with AgentCore."
            )

from .guardrails import enforce_guardrails
from .models import PolicyDocument
from .fast_collector import generate_policy_fast

app = BedrockAgentCoreApp()


GUARDRAIL_PRESETS = {
    "none": {
        "blocked_actions": [],
        "required_conditions": {},
        "disallowed_services": [],
    },
    "sandbox": {
        "blocked_actions": ["iam:PassRole"],
        "required_conditions": {},
        "disallowed_services": [],
    },
    "prod": {
        "blocked_actions": ["iam:*", "sts:AssumeRole"],
        "required_conditions": {"StringEquals": {"aws:RequestedRegion": "us-east-1"}},
        "disallowed_services": ["iam", "organizations"],
    },
}


def _enforce(payload: Dict[str, Any]) -> Dict[str, Any]:
    policy_payload = payload.get("policy")
    if not policy_payload:
        return {"error": "Missing 'policy' in payload"}

    preset = (payload.get("preset") or "sandbox").lower()
    if preset not in GUARDRAIL_PRESETS:
        preset = "sandbox"
    cfg = GUARDRAIL_PRESETS[preset].copy()

    extras = payload.get("extras") or {}
    if "blocked_actions" in extras:
        cfg["blocked_actions"] = list(cfg["blocked_actions"]) + list(extras["blocked_actions"] or [])
    if "required_conditions" in extras:
        merged = dict(cfg["required_conditions"])
        merged.update(extras["required_conditions"] or {})
        cfg["required_conditions"] = merged
    if "disallowed_services" in extras:
        cfg["disallowed_services"] = list(cfg["disallowed_services"]) + list(
            extras["disallowed_services"] or []
        )

    policy = PolicyDocument(**policy_payload)
    sanitized, violations = enforce_guardrails(
        policy,
        blocked_actions=cfg["blocked_actions"],
        required_conditions=cfg["required_conditions"],
        disallowed_services=cfg["disallowed_services"],
    )

    return {
        "sanitized_policy": sanitized.model_dump(by_alias=True),
        "violations": [v.model_dump() for v in violations],
        "preset": preset,
    }


def _analyze_fast(payload: Dict[str, Any]) -> Dict[str, Any]:
    role_arn = payload.get("roleArn") or payload.get("role_arn")
    if not role_arn:
        return {"error": "Missing 'roleArn' in payload"}
    usage_days = int(payload.get("usageDays") or 30)
    region = payload.get("region") or os.getenv("AWS_REGION", "us-east-1")

    policy = generate_policy_fast(role_arn=role_arn, usage_days=usage_days, region=region)
    return {"policy": policy.model_dump(by_alias=True)}


@app.entrypoint
def invoke(payload: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Single AgentCore entrypoint with action dispatch.

    Expected payload:
      { "action": "enforce_policy_guardrails" | "analyze_fast_policy", ... }
    """
    action = (payload.get("action") or "").strip()
    if action == "enforce_policy_guardrails":
        return _enforce(payload)
    if action == "analyze_fast_policy":
        return _analyze_fast(payload)
    return {"error": "Missing or unsupported 'action'", "supported": ["enforce_policy_guardrails", "analyze_fast_policy"]}


if __name__ == "__main__":  # pragma: no cover
    # Allows local runs to validate imports; real serving happens in AgentCore Runtime
    app.run()
