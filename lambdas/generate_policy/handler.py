"""
Lambda handler for IAM Access Analyzer policy generation.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from alpha_agent.collector import PolicyGenerationError, generate_policy
from alpha_agent.models import PolicyGenerationRequest

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Start IAM Access Analyzer policy generation and poll for results.

    Expected event payload:
    {
        "analyzer_arn": "arn:aws:access-analyzer:...",
        "resource_arn": "arn:aws:iam::123456789012:role/ExampleRole",
        "cloudtrail_access_role_arn": "arn:aws:iam::...",
        "cloudtrail_trail_arns": ["arn:aws:cloudtrail:..."],
        "usage_period_days": 30
    }

    Returns:
    {
        "statusCode": 200,
        "policy": { "Version": "2012-10-17", "Statement": [...] }
    }
    """
    try:
        request = PolicyGenerationRequest(
            analyzer_arn=event["analyzer_arn"],
            resource_arn=event["resource_arn"],
            cloudtrail_access_role_arn=event["cloudtrail_access_role_arn"],
            cloudtrail_trail_arns=event["cloudtrail_trail_arns"],
            usage_period_days=event.get("usage_period_days", 30),
        )

        policy_document = generate_policy(
            request,
            poll_interval=int(os.getenv("POLL_INTERVAL_SECONDS", "10")),
            timeout_seconds=int(os.getenv("TIMEOUT_SECONDS", "600")),
        )

        LOGGER.info("Successfully generated policy for %s", request.resource_arn)

        return {
            "statusCode": 200,
            "policy": policy_document.model_dump(by_alias=True),
        }

    except PolicyGenerationError as err:
        LOGGER.error("Policy generation failed: %s", err)
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
        LOGGER.exception("Unexpected error during policy generation")
        return {
            "statusCode": 500,
            "error": f"Unexpected error: {err}",
        }
