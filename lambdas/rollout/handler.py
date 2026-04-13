"""
Lambda handler for policy rollout execution.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict
from datetime import datetime

import boto3

import alpha_agent.rollout as rollout_mod
from alpha_agent.models import PolicyDocument, RolloutStage
from alpha_agent.rollout import RolloutError

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

METRIC_NAMESPACE = os.getenv("CLOUDWATCH_NAMESPACE", "ALPHA/IAM")


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
        stage_name = event.get("stage")
        proposal_data = event.get("proposal")
        role_arn = event.get("role_arn") or (proposal_data or {}).get("role_arn")
        baseline_data = event.get("baselinePolicy")

        if stage_name is None:
            raise KeyError("stage")
        if proposal_data is None:
            raise KeyError("proposal")

        if not role_arn:
            raise KeyError("role_arn")

        policy_data = proposal_data["proposed_policy"]
        policy = PolicyDocument(**policy_data)
        stage = RolloutStage(stage_name)

        description = proposal_data.get("rationale", "ALPHA policy update")

        outcome = rollout_mod.orchestrate_rollout(
            role_arn=role_arn,
            policy_document=policy,
            stage=stage,
            metrics_collector=lambda: _collect_cloudwatch_metrics(
                role_arn, METRIC_NAMESPACE
            ),
            description=description,
        )

        # Publish metrics
        try:
            cw = boto3.client("cloudwatch")
            cw.put_metric_data(
                Namespace=METRIC_NAMESPACE,
                MetricData=[
                    {
                        "MetricName": "ErrorRate",
                        "Dimensions": [
                            {"Name": "RoleArn", "Value": role_arn},
                            {"Name": "Stage", "Value": stage.value},
                        ],
                        "Timestamp": datetime.utcnow(),
                        "Value": outcome.metrics.get("error_rate", 0.0),
                        "Unit": "Percent",
                    }
                ],
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            LOGGER.warning("Failed to publish CloudWatch metric: %s", err)

        if not outcome.succeeded and baseline_data:
            try:
                baseline_policy = PolicyDocument(**baseline_data)
                rollout_mod.restore_policy(role_arn, baseline_policy)
                LOGGER.info("Baseline policy restored after failure for %s", role_arn)
            except Exception as err:  # pylint: disable=broad-exception-caught
                LOGGER.error("Failed to restore baseline policy: %s", err)

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
