"""
Lambda handler for guardrail enforcement on policy proposals.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from alpha_agent.guardrails import enforce_guardrails
from alpha_agent.models import PolicyDocument

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def _parse_list_env(var_name: str, default: List[str]) -> List[str]:
    """Parse comma-separated environment variable into list."""
    value = os.getenv(var_name, "")
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_dict_env(var_name: str, default: Dict) -> Dict:
    """Parse JSON environment variable into dict."""
    value = os.getenv(var_name, "")
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        LOGGER.warning("Failed to parse %s as JSON, using default", var_name)
        return default


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Enforce organizational guardrails on a proposed policy.

    Expected event payload:
    {
        "policy": {
            "proposed_policy": {
                "Version": "2012-10-17",
                "Statement": [...]
            },
            "rationale": "...",
            ...
        }
    }

    Returns:
    {
        "statusCode": 200,
        "sanitized_proposal": {
            "proposed_policy": {...},
            "rationale": "...",
            "guardrail_violations": [...]
        }
    }
    """
    try:
        proposal_data = event["policy"]
        policy_data = proposal_data.get("proposed_policy")

        if not policy_data:
            raise KeyError("proposed_policy")

        policy = PolicyDocument(**policy_data)

        # Load guardrail configuration from environment
        blocked_actions = _parse_list_env("GUARDRAIL_BLOCKED_ACTIONS", ["iam:PassRole"])
        required_conditions = _parse_dict_env(
            "GUARDRAIL_REQUIRED_CONDITIONS",
            {"StringEquals": {"aws:RequestedRegion": "us-east-1"}},
        )
        disallowed_services = _parse_list_env("GUARDRAIL_DISALLOWED_SERVICES", ["iam"])

        sanitized_policy, violations = enforce_guardrails(
            policy,
            blocked_actions=blocked_actions,
            required_conditions=required_conditions,
            disallowed_services=disallowed_services,
        )

        # Merge violations back into proposal
        sanitized_proposal = proposal_data.copy()
        sanitized_proposal["proposed_policy"] = sanitized_policy.model_dump(by_alias=True)
        sanitized_proposal["guardrail_violations"] = (
            sanitized_proposal.get("guardrail_violations", [])
            + [v.model_dump() for v in violations]
        )

        LOGGER.info("Applied guardrails, found %d violations", len(violations))

        return {
            "statusCode": 200,
            "sanitized_proposal": sanitized_proposal,
        }

    except KeyError as err:
        LOGGER.error("Missing required field: %s", err)
        return {
            "statusCode": 400,
            "error": f"Missing required field: {err}",
        }
    except Exception as err:  # pylint: disable=broad-exception-caught
        LOGGER.exception("Unexpected error during guardrail enforcement")
        return {
            "statusCode": 500,
            "error": f"Unexpected error: {err}",
        }
