from __future__ import annotations

import json
import logging
import time
from typing import Dict, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .models import PolicyDocument, RolloutOutcome, RolloutStage

LOGGER = logging.getLogger(__name__)


class RolloutError(RuntimeError):
    """Raised when rollout actions fail."""


def _build_iam_client() -> boto3.client:
    cfg = Config(
        connect_timeout=5,
        read_timeout=30,
        retries={"max_attempts": 10, "mode": "standard"},
    )
    return boto3.client("iam", config=cfg)


def _role_name_from_arn(role_arn: str) -> str:
    return role_arn.split("/")[-1]


def stage_policy_version(
    role_arn: str,
    policy_document: PolicyDocument,
    description: str,
    client: Optional[boto3.client] = None,
    policy_name: str = "ALPHAActive",
) -> str:
    """
    Upsert an inline policy attached to the role.

    Returns the policy name for reference. Keeps policy in place (no auto-delete).
    """
    client = client or _build_iam_client()
    role_name = _role_name_from_arn(role_arn)

    try:
        client.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document.model_dump(by_alias=True)),
        )
    except ClientError as err:
        raise RolloutError(f"Failed to stage policy for {role_name}: {err}") from err

    LOGGER.info("Staged policy %s on role %s", policy_name, role_name)
    return policy_name


def evaluate_stage(stage: RolloutStage, metrics: Dict[str, float]) -> bool:
    """
    Simple heuristic: fail if error metrics exceed thresholds.
    """
    error_rate = metrics.get("error_rate", 0)
    if stage == RolloutStage.SANDBOX:
        return error_rate < 0.05
    if stage == RolloutStage.CANARY:
        return error_rate < 0.02
    if stage == RolloutStage.TARGET:
        return error_rate < 0.01
    return True


def orchestrate_rollout(
    role_arn: str,
    policy_document: PolicyDocument,
    stage: RolloutStage,
    metrics_collector,
    description: str,
) -> RolloutOutcome:
    """
    Attach policy for a given stage and evaluate success based on metrics.

    `metrics_collector` should be a callable returning a dictionary of metrics for
    the role (e.g., CloudWatch alarms, custom health signals).
    """
    policy_name = stage_policy_version(role_arn, policy_document, description)
    try:
        metrics = metrics_collector()
        succeeded = evaluate_stage(stage, metrics)
        if not succeeded:
            raise RolloutError(f"Stage {stage.value} failed health checks: {metrics}")
        return RolloutOutcome(stage=stage, succeeded=True, metrics=metrics)
    except Exception as err:  # pylint: disable=broad-exception-caught
        LOGGER.error("Rollout stage %s failed: %s", stage, err)
        return RolloutOutcome(
            stage=stage, succeeded=False, error=str(err), metrics={}
        )


def restore_policy(role_arn: str, policy_document: PolicyDocument, client: Optional[boto3.client] = None) -> None:
    """
    Restore a baseline inline policy (used for rollback).
    """
    client = client or _build_iam_client()
    role_name = _role_name_from_arn(role_arn)
    try:
        client.put_role_policy(
            RoleName=role_name,
            PolicyName="ALPHAActive",
            PolicyDocument=json.dumps(policy_document.model_dump(by_alias=True)),
        )
        LOGGER.info("Restored baseline policy for %s", role_name)
    except ClientError as err:
        raise RolloutError(f"Failed to restore policy for {role_name}: {err}") from err
