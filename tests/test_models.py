"""
Tests for alpha_agent.models module.

Tests all Pydantic models, enums, and data classes used throughout ALPHA.
"""
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from alpha_agent.models import (
    Environment,
    PolicyGenerationRequest,
    PolicyDocument,
    PolicyDiff,
    GuardrailViolation,
    RiskSignal,
    PolicyProposal,
    ApprovalRecord,
    RolloutStage,
    RolloutPlan,
    RolloutOutcome,
    NotificationPayload,
)


class TestEnvironmentEnum:
    """Tests for Environment enum."""

    def test_environment_values(self):
        assert Environment.SANDBOX.value == "sandbox"
        assert Environment.CANARY.value == "canary"
        assert Environment.PRODUCTION.value == "production"

    def test_environment_from_string(self):
        assert Environment("sandbox") == Environment.SANDBOX
        assert Environment("canary") == Environment.CANARY
        assert Environment("production") == Environment.PRODUCTION

    def test_environment_invalid_value(self):
        with pytest.raises(ValueError):
            Environment("invalid")


class TestRolloutStageEnum:
    """Tests for RolloutStage enum."""

    def test_rollout_stage_values(self):
        assert RolloutStage.DRY_RUN.value == "dry-run"
        assert RolloutStage.SANDBOX.value == "sandbox"
        assert RolloutStage.CANARY.value == "canary"
        assert RolloutStage.TARGET.value == "target"

    def test_rollout_stage_from_string(self):
        assert RolloutStage("dry-run") == RolloutStage.DRY_RUN
        assert RolloutStage("sandbox") == RolloutStage.SANDBOX

    def test_rollout_stage_invalid_value(self):
        with pytest.raises(ValueError):
            RolloutStage("invalid")


class TestPolicyGenerationRequest:
    """Tests for PolicyGenerationRequest model."""

    def test_valid_request(self):
        request = PolicyGenerationRequest(
            analyzer_arn="arn:aws:access-analyzer:us-east-1:123456789012:analyzer/test",
            resource_arn="arn:aws:iam::123456789012:role/TestRole",
            cloudtrail_access_role_arn="arn:aws:iam::123456789012:role/CloudTrailRole",
            cloudtrail_trail_arns=["arn:aws:cloudtrail:us-east-1:123456789012:trail/test"],
        )
        assert request.usage_period_days == 30
        assert request.include_condition_keys is True

    def test_custom_usage_period(self):
        request = PolicyGenerationRequest(
            analyzer_arn="arn:aws:access-analyzer:us-east-1:123456789012:analyzer/test",
            resource_arn="arn:aws:iam::123456789012:role/TestRole",
            cloudtrail_access_role_arn="arn:aws:iam::123456789012:role/CloudTrailRole",
            cloudtrail_trail_arns=["arn:aws:cloudtrail:us-east-1:123456789012:trail/test"],
            usage_period_days=90,
            include_condition_keys=False,
        )
        assert request.usage_period_days == 90
        assert request.include_condition_keys is False

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            PolicyGenerationRequest(
                analyzer_arn="arn:aws:access-analyzer:us-east-1:123456789012:analyzer/test",
            )

    def test_empty_trail_arns_allowed(self):
        request = PolicyGenerationRequest(
            analyzer_arn="arn:aws:access-analyzer:us-east-1:123456789012:analyzer/test",
            resource_arn="arn:aws:iam::123456789012:role/TestRole",
            cloudtrail_access_role_arn="arn:aws:iam::123456789012:role/CloudTrailRole",
            cloudtrail_trail_arns=[],
        )
        assert request.cloudtrail_trail_arns == []


class TestPolicyDocument:
    """Tests for PolicyDocument model."""

    def test_basic_policy(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        assert policy.version == "2012-10-17"
        assert len(policy.statement) == 1

    def test_custom_version(self):
        policy = PolicyDocument(
            version="2008-10-17",
            statement=[{"Effect": "Allow", "Action": "*", "Resource": "*"}]
        )
        assert policy.version == "2008-10-17"

    def test_multiple_statements(self):
        policy = PolicyDocument(
            statement=[
                {"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"},
                {"Effect": "Deny", "Action": "iam:*", "Resource": "*"},
            ]
        )
        assert len(policy.statement) == 2

    def test_model_dump_with_alias(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:*", "Resource": "*"}]
        )
        dumped = policy.model_dump(by_alias=True)
        assert "Version" in dumped
        assert "Statement" in dumped

    def test_empty_statement_fails(self):
        with pytest.raises(ValidationError):
            PolicyDocument(statement=None)


class TestPolicyDiff:
    """Tests for PolicyDiff model."""

    def test_basic_diff(self):
        proposed = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        diff = PolicyDiff(
            proposed_policy=proposed,
            added_actions=["s3:GetObject"],
            removed_actions=["s3:*"],
            change_summary="+1 actions, -1 actions"
        )
        assert diff.existing_policy is None
        assert len(diff.added_actions) == 1
        assert len(diff.removed_actions) == 1

    def test_diff_with_existing_policy(self):
        existing = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "*", "Resource": "*"}]
        )
        proposed = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        diff = PolicyDiff(
            existing_policy=existing,
            proposed_policy=proposed,
            removed_actions=["*"],
            added_actions=["s3:GetObject"],
        )
        assert diff.existing_policy is not None

    def test_empty_diff(self):
        proposed = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        diff = PolicyDiff(proposed_policy=proposed)
        assert diff.added_actions == []
        assert diff.removed_actions == []
        assert diff.change_summary == ""


class TestGuardrailViolation:
    """Tests for GuardrailViolation model."""

    def test_basic_violation(self):
        violation = GuardrailViolation(
            code="WILDCARD_ACTION",
            message="Wildcard actions are not allowed"
        )
        assert violation.path is None

    def test_violation_with_path(self):
        violation = GuardrailViolation(
            code="MISSING_CONDITION",
            message="Condition key missing",
            path="statement[0].Condition"
        )
        assert violation.path == "statement[0].Condition"

    def test_model_dump(self):
        violation = GuardrailViolation(
            code="TEST",
            message="Test message"
        )
        dumped = violation.model_dump()
        assert "code" in dumped
        assert "message" in dumped


class TestRiskSignal:
    """Tests for RiskSignal model."""

    def test_default_values(self):
        risk = RiskSignal()
        assert risk.probability_of_break == 0.0
        assert risk.rationale == ""

    def test_custom_values(self):
        risk = RiskSignal(
            probability_of_break=0.15,
            rationale="High complexity change"
        )
        assert risk.probability_of_break == 0.15
        assert "complexity" in risk.rationale

    def test_probability_bounds(self):
        risk = RiskSignal(probability_of_break=1.0)
        assert risk.probability_of_break == 1.0

        risk_zero = RiskSignal(probability_of_break=0.0)
        assert risk_zero.probability_of_break == 0.0


class TestPolicyProposal:
    """Tests for PolicyProposal model."""

    def test_basic_proposal(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Least privilege based on usage"
        )
        assert proposal.guardrail_violations == []
        assert proposal.remediation_notes == []

    def test_full_proposal(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        violation = GuardrailViolation(code="TEST", message="Test")
        risk = RiskSignal(probability_of_break=0.05, rationale="Low risk")

        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Comprehensive analysis",
            guardrail_violations=[violation],
            risk_signal=risk,
            remediation_notes=["Check S3 bucket policy"]
        )
        assert len(proposal.guardrail_violations) == 1
        assert proposal.risk_signal.probability_of_break == 0.05
        assert len(proposal.remediation_notes) == 1


class TestApprovalRecord:
    """Tests for ApprovalRecord model."""

    def test_approved_record(self):
        now = datetime.now(timezone.utc)
        record = ApprovalRecord(
            approver="user@example.com",
            approved=True,
            timestamp=now
        )
        assert record.comments is None

    def test_rejected_record_with_comments(self):
        now = datetime.now(timezone.utc)
        record = ApprovalRecord(
            approver="admin@example.com",
            approved=False,
            timestamp=now,
            comments="Need more review"
        )
        assert record.approved is False
        assert record.comments == "Need more review"

    def test_timestamp_serialization(self):
        now = datetime.now(timezone.utc)
        record = ApprovalRecord(
            approver="test@example.com",
            approved=True,
            timestamp=now
        )
        assert record.timestamp == now


class TestRolloutPlan:
    """Tests for RolloutPlan model."""

    def test_default_plan(self):
        plan = RolloutPlan(
            stages=[RolloutStage.SANDBOX, RolloutStage.CANARY, RolloutStage.TARGET]
        )
        assert plan.pause_between_minutes == 5

    def test_custom_pause(self):
        plan = RolloutPlan(
            stages=[RolloutStage.SANDBOX, RolloutStage.TARGET],
            pause_between_minutes=10
        )
        assert plan.pause_between_minutes == 10
        assert len(plan.stages) == 2


class TestRolloutOutcome:
    """Tests for RolloutOutcome model."""

    def test_successful_outcome(self):
        outcome = RolloutOutcome(
            stage=RolloutStage.SANDBOX,
            succeeded=True,
            metrics={"error_rate": 0.0}
        )
        assert outcome.error is None

    def test_failed_outcome(self):
        outcome = RolloutOutcome(
            stage=RolloutStage.CANARY,
            succeeded=False,
            error="Error rate exceeded threshold",
            metrics={"error_rate": 0.15}
        )
        assert outcome.succeeded is False
        assert "threshold" in outcome.error

    def test_empty_metrics(self):
        outcome = RolloutOutcome(
            stage=RolloutStage.TARGET,
            succeeded=True
        )
        assert outcome.metrics == {}


class TestNotificationPayload:
    """Tests for NotificationPayload model."""

    def test_basic_notification(self):
        payload = NotificationPayload(
            channel="slack",
            message="Policy update ready for review"
        )
        assert payload.metadata == {}

    def test_notification_with_metadata(self):
        payload = NotificationPayload(
            channel="slack",
            message="Approval required",
            metadata={"risk": "low", "role": "TestRole"}
        )
        assert payload.metadata["risk"] == "low"

    def test_model_dump(self):
        payload = NotificationPayload(
            channel="email",
            message="Test"
        )
        dumped = payload.model_dump()
        assert "channel" in dumped
        assert "message" in dumped
        assert "metadata" in dumped
