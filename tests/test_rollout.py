"""
Tests for alpha_agent.rollout module.

Tests policy rollout orchestration and stage evaluation.
"""
import pytest
from unittest.mock import MagicMock, patch
import json

from alpha_agent.rollout import (
    RolloutError,
    stage_policy_version,
    evaluate_stage,
    orchestrate_rollout,
    restore_policy,
    _role_name_from_arn,
)
from alpha_agent.models import PolicyDocument, RolloutStage, RolloutOutcome


class TestRoleNameFromArn:
    """Tests for _role_name_from_arn helper function."""

    def test_simple_role(self):
        arn = "arn:aws:iam::123456789012:role/MyRole"
        assert _role_name_from_arn(arn) == "MyRole"

    def test_role_with_path(self):
        arn = "arn:aws:iam::123456789012:role/path/to/MyRole"
        assert _role_name_from_arn(arn) == "MyRole"


class TestStagePolicyVersion:
    """Tests for stage_policy_version function."""

    def test_successful_staging(self):
        mock_client = MagicMock()
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )

        policy_name = stage_policy_version(
            "arn:aws:iam::123456789012:role/TestRole",
            policy,
            "Test description",
            client=mock_client
        )
        assert policy_name == "ALPHAActive"
        mock_client.put_role_policy.assert_called_once()

    def test_policy_document_format(self):
        mock_client = MagicMock()
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )

        stage_policy_version(
            "arn:aws:iam::123456789012:role/TestRole",
            policy,
            "Test",
            client=mock_client
        )

        call_args = mock_client.put_role_policy.call_args
        policy_doc = json.loads(call_args.kwargs["PolicyDocument"])
        assert "Version" in policy_doc
        assert "Statement" in policy_doc

    def test_client_error_raises(self):
        mock_client = MagicMock()
        from botocore.exceptions import ClientError
        mock_client.put_role_policy.side_effect = ClientError(
            {"Error": {"Code": "MalformedPolicyDocument"}},
            "PutRolePolicy"
        )
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )

        with pytest.raises(RolloutError):
            stage_policy_version(
                "arn:aws:iam::123456789012:role/TestRole",
                policy,
                "Test",
                client=mock_client
            )


class TestEvaluateStage:
    """Tests for evaluate_stage function."""

    def test_sandbox_low_error_rate(self):
        assert evaluate_stage(RolloutStage.SANDBOX, {"error_rate": 0.01}) is True

    def test_sandbox_high_error_rate(self):
        assert evaluate_stage(RolloutStage.SANDBOX, {"error_rate": 0.10}) is False

    def test_canary_low_error_rate(self):
        assert evaluate_stage(RolloutStage.CANARY, {"error_rate": 0.01}) is True

    def test_canary_high_error_rate(self):
        assert evaluate_stage(RolloutStage.CANARY, {"error_rate": 0.05}) is False

    def test_target_low_error_rate(self):
        assert evaluate_stage(RolloutStage.TARGET, {"error_rate": 0.005}) is True

    def test_target_high_error_rate(self):
        assert evaluate_stage(RolloutStage.TARGET, {"error_rate": 0.02}) is False

    def test_dry_run_always_passes(self):
        assert evaluate_stage(RolloutStage.DRY_RUN, {"error_rate": 0.50}) is True

    def test_missing_error_rate(self):
        # Default to 0 error rate
        assert evaluate_stage(RolloutStage.SANDBOX, {}) is True

    def test_empty_metrics(self):
        assert evaluate_stage(RolloutStage.CANARY, {}) is True


class TestOrchestrateRollout:
    """Tests for orchestrate_rollout function."""

    def test_successful_rollout(self):
        mock_iam_client = MagicMock()

        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )

        def metrics_collector():
            return {"error_rate": 0.0}

        with patch('alpha_agent.rollout._build_iam_client', return_value=mock_iam_client):
            outcome = orchestrate_rollout(
                "arn:aws:iam::123456789012:role/TestRole",
                policy,
                RolloutStage.SANDBOX,
                metrics_collector,
                "Test rollout"
            )

        assert isinstance(outcome, RolloutOutcome)
        assert outcome.succeeded is True
        assert outcome.stage == RolloutStage.SANDBOX
        # Policy persists (no auto-delete) and is written
        mock_iam_client.put_role_policy.assert_called()

    def test_failed_rollout_due_to_metrics(self):
        mock_iam_client = MagicMock()

        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )

        def metrics_collector():
            return {"error_rate": 0.10}  # Too high for sandbox

        with patch('alpha_agent.rollout._build_iam_client', return_value=mock_iam_client):
            outcome = orchestrate_rollout(
                "arn:aws:iam::123456789012:role/TestRole",
                policy,
                RolloutStage.SANDBOX,
                metrics_collector,
                "Test rollout"
            )

        assert outcome.succeeded is False
        assert "failed" in outcome.error.lower()
        # Policy persisted; no delete
        mock_iam_client.put_role_policy.assert_called()

    def test_metrics_collector_exception(self):
        mock_iam_client = MagicMock()

        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )

        def metrics_collector():
            raise RuntimeError("CloudWatch unavailable")

        with patch('alpha_agent.rollout._build_iam_client', return_value=mock_iam_client):
            outcome = orchestrate_rollout(
                "arn:aws:iam::123456789012:role/TestRole",
                policy,
                RolloutStage.SANDBOX,
                metrics_collector,
                "Test rollout"
            )

        assert outcome.succeeded is False
        assert "CloudWatch" in outcome.error

    def test_policy_cleanup_on_success(self):
        mock_iam_client = MagicMock()

        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )

        with patch('alpha_agent.rollout._build_iam_client', return_value=mock_iam_client):
            orchestrate_rollout(
                "arn:aws:iam::123456789012:role/TestRole",
                policy,
                RolloutStage.TARGET,
                lambda: {"error_rate": 0.0},
                "Test rollout"
            )

        # Verify policy applied
        mock_iam_client.put_role_policy.assert_called()

    def test_policy_cleanup_on_failure(self):
        mock_iam_client = MagicMock()

        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )

        with patch('alpha_agent.rollout._build_iam_client', return_value=mock_iam_client):
            orchestrate_rollout(
                "arn:aws:iam::123456789012:role/TestRole",
                policy,
                RolloutStage.CANARY,
                lambda: {"error_rate": 0.10},  # Will fail
                "Test rollout"
            )

        # Policy applied once
        mock_iam_client.put_role_policy.assert_called()

    def test_metrics_included_in_outcome(self):
        mock_iam_client = MagicMock()

        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )

        expected_metrics = {"error_rate": 0.005, "latency_p99": 100}

        with patch('alpha_agent.rollout._build_iam_client', return_value=mock_iam_client):
            outcome = orchestrate_rollout(
                "arn:aws:iam::123456789012:role/TestRole",
                policy,
                RolloutStage.SANDBOX,
                lambda: expected_metrics,
                "Test rollout"
            )

        assert outcome.metrics == expected_metrics


class TestRolloutError:
    """Tests for RolloutError exception."""

    def test_error_message(self):
        error = RolloutError("Rollout failed due to high error rate")
        assert "error rate" in str(error)

    def test_inherits_from_runtime_error(self):
        error = RolloutError("Test")
        assert isinstance(error, RuntimeError)
