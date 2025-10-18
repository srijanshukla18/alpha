from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Environment(str, Enum):
    SANDBOX = "sandbox"
    CANARY = "canary"
    PRODUCTION = "production"


class PolicyGenerationRequest(BaseModel):
    analyzer_arn: str = Field(..., description="ARN of the IAM Access Analyzer.")
    resource_arn: str = Field(..., description="ARN of the IAM role to right-size.")
    cloudtrail_access_role_arn: str = Field(
        ...,
        description="Role ARN that Access Analyzer assumes to read CloudTrail data.",
    )
    cloudtrail_trail_arns: List[str] = Field(
        ...,
        description="CloudTrail trail ARNs that captured the role's activity.",
    )
    usage_period_days: int = Field(
        30, description="Number of days of activity to include when generating policies."
    )
    include_condition_keys: bool = Field(
        True, description="Whether to include detected condition keys in the policy."
    )


class PolicyDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=None)

    version: str = Field("2012-10-17", alias="Version")
    statement: List[Dict[str, Any]] = Field(..., alias="Statement")


class PolicyDiff(BaseModel):
    existing_policy: Optional[PolicyDocument] = None
    proposed_policy: PolicyDocument
    added_actions: List[str] = Field(default_factory=list)
    removed_actions: List[str] = Field(default_factory=list)
    change_summary: str = ""


class GuardrailViolation(BaseModel):
    code: str
    message: str
    path: Optional[str] = None


class RiskSignal(BaseModel):
    probability_of_break: float = Field(
        0.0, description="0-1 range representing the likelihood of causing breakage."
    )
    rationale: str = Field(default="")


class PolicyProposal(BaseModel):
    proposed_policy: PolicyDocument
    rationale: str
    guardrail_violations: List[GuardrailViolation] = Field(default_factory=list)
    risk_signal: RiskSignal = Field(default_factory=RiskSignal)
    remediation_notes: List[str] = Field(default_factory=list)


class ApprovalRecord(BaseModel):
    approver: str
    approved: bool
    timestamp: datetime
    comments: Optional[str] = None


class RolloutStage(str, Enum):
    DRY_RUN = "dry-run"
    SANDBOX = "sandbox"
    CANARY = "canary"
    TARGET = "target"


class RolloutPlan(BaseModel):
    stages: List[RolloutStage]
    pause_between_minutes: int = 5


class RolloutOutcome(BaseModel):
    stage: RolloutStage
    succeeded: bool
    error: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)


class NotificationPayload(BaseModel):
    channel: str
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
