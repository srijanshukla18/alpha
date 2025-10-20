"""
Judge Mode - Deterministic offline simulation for demos and testing.

Provides mock data that mimics real AWS API responses without requiring credentials.
Perfect for hackathon demos, CI testing, and offline development.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from alpha_agent.models import PolicyDocument, PolicyProposal, RiskSignal, GuardrailViolation

LOGGER = logging.getLogger(__name__)

# Mock CloudTrail activity for a typical over-privileged CI role
MOCK_CLOUDTRAIL_ACTIVITY = {
    "s3:GetObject": 150,
    "s3:ListBucket": 45,
    "s3:PutObject": 12,
    "dynamodb:Query": 200,
    "dynamodb:GetItem": 350,
    "dynamodb:PutItem": 89,
    "logs:PutLogEvents": 500,
    "logs:CreateLogStream": 24,
}

MOCK_CURRENT_POLICY = PolicyDocument(
    version="2012-10-17",
    statement=[
        {
            "Effect": "Allow",
            "Action": "*",
            "Resource": "*",
        }
    ],
)

MOCK_PROPOSED_POLICY = PolicyDocument(
    version="2012-10-17",
    statement=[
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:ListBucket", "s3:PutObject"],
            "Resource": [
                "arn:aws:s3:::app-data-bucket",
                "arn:aws:s3:::app-data-bucket/*",
            ],
            "Condition": {
                "StringEquals": {
                    "aws:PrincipalOrgID": "o-abc123xyz"
                }
            },
        },
        {
            "Effect": "Allow",
            "Action": ["dynamodb:Query", "dynamodb:GetItem", "dynamodb:PutItem"],
            "Resource": "arn:aws:dynamodb:us-east-1:123456789012:table/user-sessions",
        },
        {
            "Effect": "Allow",
            "Action": ["logs:PutLogEvents", "logs:CreateLogStream"],
            "Resource": "arn:aws:logs:us-east-1:123456789012:log-group:/aws/lambda/app:*",
        },
    ],
)


class JudgeModeProvider:
    """
    Provides deterministic mock data for offline ALPHA demonstrations.

    All methods return data structures identical to real AWS API responses,
    but without making actual API calls.
    """

    def __init__(self, seed: int = 42):
        """Initialize with optional seed for reproducibility."""
        self.seed = seed
        LOGGER.info("Judge mode active - using deterministic mock data")

    def get_cloudtrail_activity(
        self,
        role_arn: str,
        usage_days: int = 30,
    ) -> Dict[str, int]:
        """
        Return mock CloudTrail activity statistics.

        Simulates IAM Access Analyzer's policy generation analysis.
        """
        LOGGER.info("JUDGE MODE: Returning mock CloudTrail activity (%d days)", usage_days)
        return MOCK_CLOUDTRAIL_ACTIVITY.copy()

    def generate_policy_from_activity(
        self,
        activity: Dict[str, int],
        role_arn: str,
    ) -> PolicyDocument:
        """
        Return mock generated policy based on activity.

        Simulates Access Analyzer's GeneratePolicy API.
        """
        LOGGER.info("JUDGE MODE: Generating mock least-privilege policy")
        return MOCK_PROPOSED_POLICY.model_copy(deep=True)

    def get_current_policy(self, role_arn: str) -> PolicyDocument:
        """
        Return mock current policy (wildcard permissions).

        Simulates IAM GetRolePolicy API.
        """
        LOGGER.info("JUDGE MODE: Returning mock current policy")
        return MOCK_CURRENT_POLICY.model_copy(deep=True)

    def invoke_bedrock_reasoning(
        self,
        policy: PolicyDocument,
        context: Dict[str, Any],
    ) -> PolicyProposal:
        """
        Return mock Bedrock reasoning response.

        Simulates Claude Sonnet 4.5 policy analysis.
        """
        LOGGER.info("JUDGE MODE: Simulating Bedrock reasoning")

        return PolicyProposal(
            proposed_policy=MOCK_PROPOSED_POLICY.model_copy(deep=True),
            rationale=(
                "Based on 30 days of CloudTrail analysis (1,245 datapoints), this role "
                "exhibits access patterns for S3 (read/write to app-data-bucket), "
                "DynamoDB (CRUD on user-sessions table), and CloudWatch Logs (application logging). "
                "The proposed policy scopes permissions to specific ARNs and adds organizational "
                "boundary conditions to prevent cross-org access."
            ),
            risk_signal=RiskSignal(
                probability_of_break=0.05,
                rationale=(
                    "High confidence assessment based on comprehensive telemetry. "
                    "Added s3:ListBucket for pagination support despite no direct observations. "
                    "All observed actions mapped to specific resources. "
                    "No missing dependencies detected."
                ),
            ),
            guardrail_violations=[],  # Clean policy
            remediation_notes=[
                "Ensure S3 bucket policy allows cross-account access if needed",
                "Monitor DynamoDB throttling after deployment",
                "Validate log group permissions during canary phase",
            ],
        )

    def start_step_functions_execution(
        self,
        state_machine_arn: str,
        input_payload: Dict[str, Any],
    ) -> str:
        """
        Return mock Step Functions execution ARN.

        Simulates StartExecution API.
        """
        LOGGER.info("JUDGE MODE: Simulating Step Functions execution start")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"arn:aws:states:us-east-1:123456789012:execution:AlphaSM:mock-{timestamp}"

    def check_approval_status(self, proposal_id: str) -> bool:
        """
        Return mock approval status.

        In judge mode, always returns approved for demo flow.
        """
        LOGGER.info("JUDGE MODE: Returning mock approval (approved=True)")
        return True

    def record_audit_trail(self, audit_data: Dict[str, Any]) -> None:
        """
        Mock DynamoDB audit record creation.

        In judge mode, just logs the data.
        """
        LOGGER.info("JUDGE MODE: Would record audit: %s", json.dumps(audit_data, indent=2))


def is_judge_mode() -> bool:
    """
    Detect if we're running in judge mode.

    Checks for:
    1. --judge-mode CLI flag (handled by command)
    2. ALPHA_JUDGE_MODE environment variable
    """
    import os
    return os.getenv("ALPHA_JUDGE_MODE", "").lower() in ("1", "true", "yes")


def get_provider() -> JudgeModeProvider | None:
    """
    Get judge mode provider if active, otherwise None.
    """
    if is_judge_mode():
        return JudgeModeProvider()
    return None
