"""
Lambda handler for checking human approval status.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

from alpha_agent.approvals import ApprovalStore, ApprovalStoreError

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Check if a policy proposal has been approved by a human.

    Expected event payload:
    {
        "proposal_id": "arn:aws:iam::123456789012:role/ExampleRole"
    }

    Returns:
    {
        "statusCode": 200,
        "approved": true,
        "approver": "user@example.com",
        "timestamp": "2025-01-15T10:30:00Z",
        "comments": "Approved for deployment"
    }
    """
    try:
        proposal_id = event["proposal_id"]
        table_name = os.getenv("APPROVAL_TABLE_NAME")

        if not table_name:
            raise ValueError("APPROVAL_TABLE_NAME environment variable not set")

        store = ApprovalStore(table_name)
        latest_approval = store.latest(proposal_id)

        if latest_approval:
            LOGGER.info(
                "Found approval for %s by %s", proposal_id, latest_approval.approver
            )
            return {
                "statusCode": 200,
                "approved": latest_approval.approved,
                "approver": latest_approval.approver,
                "timestamp": latest_approval.timestamp.isoformat(),
                "comments": latest_approval.comments or "",
            }

        LOGGER.info("No approval found for %s", proposal_id)
        return {
            "statusCode": 200,
            "approved": False,
        }

    except ApprovalStoreError as err:
        LOGGER.error("Failed to check approval: %s", err)
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
        LOGGER.exception("Unexpected error checking approval")
        return {
            "statusCode": 500,
            "error": f"Unexpected error: {err}",
        }
