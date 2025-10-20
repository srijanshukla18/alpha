from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError

from .models import PolicyDocument, PolicyGenerationRequest

LOGGER = logging.getLogger(__name__)


class PolicyGenerationError(RuntimeError):
    """Raised when IAM Access Analyzer policy generation fails."""


def _build_access_analyzer_client() -> boto3.client:
    return boto3.client("accessanalyzer")


def start_policy_generation(
    request: PolicyGenerationRequest, client: Optional[boto3.client] = None
) -> str:
    """
    Start an IAM Access Analyzer job to generate least-privilege policy.

    Returns the job identifier to poll for completion.
    """
    client = client or _build_access_analyzer_client()
    try:
        start_time = datetime.now(timezone.utc) - timedelta(days=request.usage_period_days)
        end_time = datetime.now(timezone.utc)
        # AWS requires datetime in specific format: yyyy-MM-dd'T'HH:mm:ss.SSSZ
        start_time_str = start_time.strftime('%Y-%m-%dT%H:%M:%S') + '.000Z'
        end_time_str = end_time.strftime('%Y-%m-%dT%H:%M:%S') + '.000Z'
        response = client.start_policy_generation(
            clientToken=f"{request.resource_arn}:{int(time.time())}",
            cloudTrailDetails={
                "accessRole": request.cloudtrail_access_role_arn,
                "endTime": end_time_str,
                "startTime": start_time_str,
                "trails": [
                    {"cloudTrailArn": arn, "regions": [], "allRegions": True}
                    for arn in request.cloudtrail_trail_arns
                ],
            },
            policyGenerationDetails={
                "principalArn": request.resource_arn,
            },
        )
    except ClientError as err:
        raise PolicyGenerationError(f"Unable to start policy generation: {err}") from err

    job_id = response["jobId"]
    LOGGER.info("Started policy generation job %s", job_id)
    return job_id


def wait_for_policy_json(
    job_id: str,
    client: Optional[boto3.client] = None,
    poll_interval: int = 10,
    timeout_seconds: int = 1800,
) -> Dict:
    """
    Poll for job completion and return the generated policy JSON.

    The Access Analyzer API returns a JSON document as a string; this function
    deserializes it before returning.
    """
    client = client or _build_access_analyzer_client()
    started = time.time()

    while True:
        try:
            response = client.get_generated_policy(jobId=job_id)
        except ClientError as err:
            raise PolicyGenerationError(
                f"Unable to retrieve policy for job {job_id}: {err}"
            ) from err

        status = response["jobDetails"]["status"]
        if status == "SUCCEEDED":
            document = json.loads(response["generatedPolicyResult"]["policy"])
            LOGGER.info("Policy generation job %s succeeded", job_id)
            return document
        if status == "FAILED":
            reason = response["jobDetails"].get("failureReason", "unknown")
            raise PolicyGenerationError(
                f"Policy generation job {job_id} failed: {reason}"
            )

        if time.time() - started > timeout_seconds:
            raise PolicyGenerationError(
                f"Policy generation job {job_id} timed out after {timeout_seconds}s"
            )

        LOGGER.debug("Job %s still running, sleeping %s seconds", job_id, poll_interval)
        time.sleep(poll_interval)


def generate_policy(
    request: PolicyGenerationRequest,
    client: Optional[boto3.client] = None,
    poll_interval: int = 10,
    timeout_seconds: int = 1800,
) -> PolicyDocument:
    """Convenience wrapper to kick off and retrieve the policy document."""
    client = client or _build_access_analyzer_client()
    job_id = start_policy_generation(request, client=client)
    policy_json = wait_for_policy_json(
        job_id=job_id, client=client, poll_interval=poll_interval, timeout_seconds=timeout_seconds
    )
    statements = policy_json.get("Statement", [])
    if not statements:
        raise PolicyGenerationError("Generated policy document missing Statement entries.")
    return PolicyDocument(
        statement=statements,
        version=policy_json.get("Version", "2012-10-17"),
    )
