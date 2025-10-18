"""
Lambda handler for Bedrock reasoning over generated policies.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

from alpha_agent.models import PolicyDocument
from alpha_agent.reasoning import BedrockReasoner, BedrockReasoningError

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Invoke Bedrock model to reason about a generated policy.

    Expected event payload:
    {
        "context": {
            "role": "arn:aws:iam::123456789012:role/ExampleRole",
            "service_owner": "team-name",
            "environment": "sandbox",
            "business_impact": "low"
        },
        "policy": {
            "Version": "2012-10-17",
            "Statement": [...]
        }
    }

    Returns:
    {
        "statusCode": 200,
        "proposal": {
            "proposed_policy": {...},
            "rationale": "...",
            "risk_signal": {...},
            "guardrail_violations": [...],
            "remediation_notes": [...]
        }
    }
    """
    try:
        context = event["context"]
        policy_data = event["policy"]

        policy = PolicyDocument(**policy_data)

        model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-5-20250929-v1:0")
        temperature = float(os.getenv("BEDROCK_TEMPERATURE", "0.2"))

        reasoner = BedrockReasoner(model_id=model_id, temperature=temperature)
        proposal = reasoner.propose_policy(context, policy)

        LOGGER.info("Successfully generated proposal for %s", context.get("role", "unknown"))

        return {
            "statusCode": 200,
            "proposal": proposal.model_dump(mode="json", by_alias=True),
        }

    except BedrockReasoningError as err:
        LOGGER.error("Bedrock reasoning failed: %s", err)
        return {
            "statusCode": 500,
            "error": str(err),
        }
    except KeyError as err:
        LOGGER.error("Missing required field: %s", err)
        return {
            "statusCode": 400,
            "error": f"Missing required field: {err}",
        }
    except Exception as err:  # pylint: disable=broad-exception-caught
        LOGGER.exception("Unexpected error during reasoning")
        return {
            "statusCode": 500,
            "error": f"Unexpected error: {err}",
        }
