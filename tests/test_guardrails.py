"""
Tests for alpha_agent.guardrails module.

Tests guardrail enforcement logic for policy sanitization.
"""
import pytest
from copy import deepcopy

from alpha_agent.guardrails import (
    enforce_guardrails,
    _ensure_list,
    WILDCARD_ACTION_VIOLATION,
    MISSING_CONDITION_VIOLATION,
    UNSUPPORTED_SERVICE_VIOLATION,
)
from alpha_agent.models import PolicyDocument, GuardrailViolation


class TestEnsureList:
    """Tests for _ensure_list helper function."""

    def test_list_input(self):
        result = _ensure_list(["a", "b"])
        assert result == ["a", "b"]

    def test_string_input(self):
        result = _ensure_list("single")
        assert result == ["single"]

    def test_empty_list(self):
        result = _ensure_list([])
        assert result == []


class TestEnforceGuardrails:
    """Tests for enforce_guardrails function."""

    def test_clean_policy_passes(self):
        policy = PolicyDocument(
            statement=[
                {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}
            ]
        )
        sanitized, violations = enforce_guardrails(
            policy,
            blocked_actions=[],
            required_conditions={},
            disallowed_services=[]
        )
        assert len(violations) == 0
        assert len(sanitized.statement) == 1

    def test_wildcard_action_removed(self):
        policy = PolicyDocument(
            statement=[
                {"Effect": "Allow", "Action": "*", "Resource": "*"}
            ]
        )
        sanitized, violations = enforce_guardrails(
            policy,
            blocked_actions=[],
            required_conditions={},
            disallowed_services=[]
        )
        assert any(v.code == WILDCARD_ACTION_VIOLATION for v in violations)
        # Wildcard action should be removed
        actions = sanitized.statement[0].get("Action", [])
        assert "*" not in actions

    def test_service_wildcard_detected(self):
        policy = PolicyDocument(
            statement=[
                {"Effect": "Allow", "Action": "s3:*", "Resource": "*"}
            ]
        )
        sanitized, violations = enforce_guardrails(
            policy,
            blocked_actions=[],
            required_conditions={},
            disallowed_services=[]
        )
        assert any(v.code == WILDCARD_ACTION_VIOLATION for v in violations)

    def test_blocked_action_removed(self):
        policy = PolicyDocument(
            statement=[
                {"Effect": "Allow", "Action": ["s3:GetObject", "iam:PassRole"], "Resource": "*"}
            ]
        )
        sanitized, violations = enforce_guardrails(
            policy,
            blocked_actions=["iam:PassRole"],
            required_conditions={},
            disallowed_services=[]
        )
        assert any(v.code == WILDCARD_ACTION_VIOLATION for v in violations)
        actions = sanitized.statement[0].get("Action", [])
        assert "iam:PassRole" not in actions
        assert "s3:GetObject" in actions

    def test_disallowed_service_flagged(self):
        policy = PolicyDocument(
            statement=[
                {"Effect": "Allow", "Action": ["iam:CreateRole", "s3:GetObject"], "Resource": "*"}
            ]
        )
        sanitized, violations = enforce_guardrails(
            policy,
            blocked_actions=[],
            required_conditions={},
            disallowed_services=["iam"]
        )
        assert any(v.code == UNSUPPORTED_SERVICE_VIOLATION for v in violations)

    def test_required_condition_added(self):
        policy = PolicyDocument(
            statement=[
                {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}
            ]
        )
        required_conditions = {"StringEquals": {"aws:RequestedRegion": "us-east-1"}}
        sanitized, violations = enforce_guardrails(
            policy,
            blocked_actions=[],
            required_conditions=required_conditions,
            disallowed_services=[]
        )
        assert any(v.code == MISSING_CONDITION_VIOLATION for v in violations)
        # Condition should be added
        conditions = sanitized.statement[0].get("Condition", {})
        assert "StringEquals" in conditions

    def test_existing_condition_preserved(self):
        policy = PolicyDocument(
            statement=[
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject"],
                    "Resource": "*",
                    "Condition": {"StringEquals": {"aws:RequestedRegion": "us-east-1"}}
                }
            ]
        )
        sanitized, violations = enforce_guardrails(
            policy,
            blocked_actions=[],
            required_conditions={"StringEquals": {"aws:RequestedRegion": "us-east-1"}},
            disallowed_services=[]
        )
        # No violation for existing condition
        cond_violations = [v for v in violations if v.code == MISSING_CONDITION_VIOLATION]
        assert len(cond_violations) == 0

    def test_multiple_statements_processed(self):
        policy = PolicyDocument(
            statement=[
                {"Effect": "Allow", "Action": "*", "Resource": "*"},
                {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"},
            ]
        )
        sanitized, violations = enforce_guardrails(
            policy,
            blocked_actions=[],
            required_conditions={},
            disallowed_services=[]
        )
        assert len(violations) >= 1  # At least one for wildcard
        assert len(sanitized.statement) == 2

    def test_multiple_resources_filtered(self):
        policy = PolicyDocument(
            statement=[
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject"],
                    "Resource": ["*", "arn:aws:s3:::bucket/*"]
                }
            ]
        )
        sanitized, violations = enforce_guardrails(
            policy,
            blocked_actions=[],
            required_conditions={},
            disallowed_services=[]
        )
        # Wildcard resource should be removed when there are specific resources
        resources = sanitized.statement[0].get("Resource", [])
        assert "*" not in resources
        assert "arn:aws:s3:::bucket/*" in resources

    def test_single_wildcard_resource_kept(self):
        policy = PolicyDocument(
            statement=[
                {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}
            ]
        )
        sanitized, violations = enforce_guardrails(
            policy,
            blocked_actions=[],
            required_conditions={},
            disallowed_services=[]
        )
        # Single wildcard resource should be kept (no specific alternatives)
        resources = sanitized.statement[0].get("Resource", [])
        assert "*" in resources or resources == "*"

    def test_violation_path_includes_index(self):
        policy = PolicyDocument(
            statement=[
                {"Effect": "Allow", "Action": "*", "Resource": "*"}
            ]
        )
        _, violations = enforce_guardrails(
            policy,
            blocked_actions=[],
            required_conditions={},
            disallowed_services=[]
        )
        for v in violations:
            if v.path:
                assert "statement[0]" in v.path

    def test_combined_violations(self):
        policy = PolicyDocument(
            statement=[
                {
                    "Effect": "Allow",
                    "Action": ["iam:PassRole", "s3:*"],
                    "Resource": "*"
                }
            ]
        )
        sanitized, violations = enforce_guardrails(
            policy,
            blocked_actions=["iam:PassRole"],
            required_conditions={"StringEquals": {"key": "value"}},
            disallowed_services=["iam"]
        )
        # Should have multiple violations
        assert len(violations) >= 2

    def test_empty_actions_after_removal(self):
        policy = PolicyDocument(
            statement=[
                {"Effect": "Allow", "Action": "*", "Resource": "*"}
            ]
        )
        sanitized, violations = enforce_guardrails(
            policy,
            blocked_actions=[],
            required_conditions={},
            disallowed_services=[]
        )
        # Actions array should exist even if wildcards are removed
        assert "Action" in sanitized.statement[0]

    def test_action_as_string_handled(self):
        policy = PolicyDocument(
            statement=[
                {"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}
            ]
        )
        sanitized, violations = enforce_guardrails(
            policy,
            blocked_actions=[],
            required_conditions={},
            disallowed_services=[]
        )
        assert len(violations) == 0

    def test_version_preserved(self):
        policy = PolicyDocument(
            version="2012-10-17",
            statement=[
                {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}
            ]
        )
        sanitized, _ = enforce_guardrails(
            policy,
            blocked_actions=[],
            required_conditions={},
            disallowed_services=[]
        )
        assert sanitized.version == "2012-10-17"
