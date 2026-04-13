"""
Tests for alpha_agent.agentcore_entrypoint module.

Tests AgentCore Runtime entrypoint functions.
"""
import pytest
from unittest.mock import MagicMock, patch

from alpha_agent.agentcore_entrypoint import (
    _enforce,
    invoke,
    GUARDRAIL_PRESETS,
)


class TestGuardrailPresets:
    """Tests for guardrail preset configurations."""

    def test_none_preset(self):
        preset = GUARDRAIL_PRESETS["none"]
        assert preset["blocked_actions"] == []
        assert preset["required_conditions"] == {}
        assert preset["disallowed_services"] == []

    def test_sandbox_preset(self):
        preset = GUARDRAIL_PRESETS["sandbox"]
        assert "iam:PassRole" in preset["blocked_actions"]

    def test_prod_preset(self):
        preset = GUARDRAIL_PRESETS["prod"]
        assert "iam:*" in preset["blocked_actions"]
        assert "iam" in preset["disallowed_services"]


class TestEnforceFunction:
    """Tests for _enforce internal function."""

    def test_missing_policy(self):
        result = _enforce({})
        assert "error" in result
        assert "policy" in result["error"].lower()

    def test_basic_enforcement(self):
        payload = {
            "policy": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
            }
        }
        result = _enforce(payload)
        assert "sanitized_policy" in result
        assert "violations" in result
        assert "preset" in result

    def test_default_preset(self):
        payload = {
            "policy": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
            }
        }
        result = _enforce(payload)
        assert result["preset"] == "sandbox"

    def test_custom_preset(self):
        payload = {
            "policy": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
            },
            "preset": "prod"
        }
        result = _enforce(payload)
        assert result["preset"] == "prod"

    def test_invalid_preset_defaults_to_sandbox(self):
        payload = {
            "policy": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
            },
            "preset": "invalid"
        }
        result = _enforce(payload)
        assert result["preset"] == "sandbox"

    def test_extras_merged(self):
        payload = {
            "policy": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": ["s3:GetObject", "ec2:StartInstance"], "Resource": "*"}]
            },
            "preset": "none",
            "extras": {
                "blocked_actions": ["ec2:StartInstance"],
                "disallowed_services": ["ec2"]
            }
        }
        result = _enforce(payload)
        # ec2 should be flagged
        assert any(v["code"] == "UNSUPPORTED_SERVICE" for v in result["violations"])

    def test_extras_conditions_merged(self):
        payload = {
            "policy": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
            },
            "preset": "none",
            "extras": {
                "required_conditions": {"StringEquals": {"key": "value"}}
            }
        }
        result = _enforce(payload)
        # Should have violation for missing condition
        assert any(v["code"] == "MISSING_CONDITION" for v in result["violations"])


class TestInvokeEntrypoint:
    """Tests for invoke entrypoint function."""

    def test_enforce_action(self):
        payload = {
            "action": "enforce_policy_guardrails",
            "policy": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
            }
        }
        result = invoke(payload, None)
        assert "sanitized_policy" in result

    def test_unsupported_action(self):
        payload = {"action": "unknown_action"}
        result = invoke(payload, None)
        assert "error" in result
        assert "supported" in result

    def test_missing_action(self):
        payload = {}
        result = invoke(payload, None)
        assert "error" in result

    def test_empty_action(self):
        payload = {"action": ""}
        result = invoke(payload, None)
        assert "error" in result

    def test_action_whitespace_stripped(self):
        payload = {
            "action": "  enforce_policy_guardrails  ",
            "policy": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
            }
        }
        result = invoke(payload, None)
        assert "sanitized_policy" in result
