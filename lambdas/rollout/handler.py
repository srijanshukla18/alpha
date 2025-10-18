"""
Lambda handler for policy rollout execution.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

import boto3

from alpha_agent.models import PolicyDocument, RolloutStage
from alpha_agent.rollout import RolloutError, orchestrate_rollout

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def _collect_cloudwatch_metrics(role_arn: str, namespace: str = "ALPHA/IAM") -> Dict[str, float]:
    """
    Collect CloudWatch metrics for the role to assess rollout health.

    In production, this would query actual CloudWatch metrics.
    For demo/testing, return synthetic metrics.
    """
    cloudwatch = boto3.client("cloudwatch")

    try:
        # Query error rate metric for the role
        response = cloudwatch.get_metric_statistics(
            Namespace=namespace,
            MetricName="IAMErrorRate",
            Dimensions=[{"Name": "RoleArn", "Value": role_arn}],
            StartTime="-PT5M",  # Last 5 minutes
            EndTime="now",
            Period=300,
            Statistics=["Average"],
        )

        datapoints = response.get("Datapoints", [])
        if datapoints:
            return {"error_rate": datapoints[0]["Average"]}

    except Exception as err:  # pylint: disable=broad-exception-caught
        LOGGER.warning("Failed to fetch CloudWatch metrics: %s", err)

    # Return safe defaults if metrics unavailable
    return {"error_rate": 0.0}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Execute a rollout stage (sandbox, canary, or target).

    Expected event payload:
    {
        "stage": "sandbox",
        "proposal": {
            "proposed_policy": {
                "Version": "2012-10-17",
                "Statement": [...]
            },
            "rationale": "...",
            ...
        },
        "role_arn": "arn:aws:iam::123456789012:role/ExampleRole"
    }

    Returns:
    {
        "statusCode": 200,
        "succeeded": true,
        "stage": "sandbox",
        "metrics": {"error_rate": 0.0}
    }
    """
    try:
        stage_name = event["stage"]
        proposal_data = event["proposal"]
        role_arn = event.get("role_arn") or proposal_data.get("role_arn")

        if not role_arn:
            raise KeyError("role_arn")

        policy_data = proposal_data["proposed_policy"]
        policy = PolicyDocument(**policy_data)
        stage = RolloutStage(stage_name)

        description = proposal_data.get("rationale", "ALPHA policy update")

        cloudwatch_namespace = os.getenv("CLOUDWATCH_NAMESPACE", "ALPHA/IAM")

        outcome = orchestrate_rollout(
            role_arn=role_arn,
            policy_document=policy,
            stage=stage,
            metrics_collector=lambda: _collect_cloudwatch_metrics(
                role_arn, cloudwatch_namespace
            ),
            description=description,
        )

        LOGGER.info("Rollout stage %s completed: %s", stage, outcome.succeeded)

        return {
            "statusCode": 200,
            "succeeded": outcome.succeeded,
            "stage": outcome.stage.value,
            "metrics": outcome.metrics,
            "error": outcome.error,
        }

    except RolloutError as err:
        LOGGER.error("Rollout execution failed: %s", err)
        return {
            "statusCode": 500,
            "succeeded": False,
            "error": str(err),
        }
    except KeyError as err:
        LOGGER.error("Missing required field: %s", err)
        return {
            "statusCode": 400,
            "error": f"Missing required field: {err}",
        }
    except Exception as err:  # pylint: disable=broad-exception-caught
        LOGGER.exception("Unexpected error during rollout")
        return {
            "statusCode": 500,
            "succeeded": False,
            "error": f"Unexpected error: {err}",
        }
