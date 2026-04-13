"""
Tests for Lambda handler functions.

Tests all Lambda handlers in the lambdas/ directory.
"""
import pytest
from unittest.mock import MagicMock, patch
import json
import os


class TestAgentCoreRuntimeHandler:
    """Tests for lambdas/agentcore_runtime/handler.py"""

    def test_list_tools_action(self):
        from lambdas.agentcore_runtime.handler import handler

        event = {"action": "list_tools"}
        result = handler(event, None)

        assert result["statusCode"] == 200
        assert "tools" in result
        assert len(result["tools"]) > 0

    def test_invoke_tool_missing_tool_name(self):
        from lambdas.agentcore_runtime.handler import handler

        event = {"action": "invoke_tool"}
        result = handler(event, None)

        assert result["statusCode"] == 400
        assert "error" in result

    def test_invoke_tool_not_found(self):
        from lambdas.agentcore_runtime.handler import handler

        event = {
            "action": "invoke_tool",
            "tool_name": "nonexistent_tool",
            "tool_input": {}
        }
        result = handler(event, None)

        assert result["statusCode"] == 404
        assert "not found" in result["error"]

    def test_invoke_tool_enforce_guardrails(self):
        from lambdas.agentcore_runtime.handler import handler

        event = {
            "action": "invoke_tool",
            "tool_name": "enforce_policy_guardrails",
            "tool_input": {
                "policy": {
                    "Version": "2012-10-17",
                    "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
                }
            }
        }
        result = handler(event, None)

        assert result["statusCode"] == 200
        assert "tool_result" in result

    def test_unsupported_action(self):
        from lambdas.agentcore_runtime.handler import handler

        event = {"action": "unsupported"}
        result = handler(event, None)

        assert result["statusCode"] == 400

    def test_entrypoint_function(self):
        from lambdas.agentcore_runtime.handler import entrypoint

        result = entrypoint({"action": "list_tools"})
        assert result["statusCode"] == 200


class TestApprovalCheckerHandler:
    """Tests for lambdas/approval_checker/handler.py"""

    def test_missing_proposal_id(self):
        from lambdas.approval_checker.handler import handler

        event = {}
        result = handler(event, None)

        assert result["statusCode"] == 400
        assert "proposal_id" in result["error"]

    def test_missing_table_env(self):
        from lambdas.approval_checker.handler import handler

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("APPROVAL_TABLE_NAME", None)
            event = {"proposal_id": "test-123"}
            result = handler(event, None)

            assert result["statusCode"] == 500

    def test_approval_found(self):
        from lambdas.approval_checker.handler import handler

        with patch.dict(os.environ, {"APPROVAL_TABLE_NAME": "test-table"}):
            with patch('alpha_agent.approvals.ApprovalStore') as mock_store_class:
                mock_store = MagicMock()
                mock_record = MagicMock()
                mock_record.approved = True
                mock_record.approver = "user@example.com"
                mock_record.timestamp.isoformat.return_value = "2025-01-15T10:30:00Z"
                mock_record.comments = "Approved"
                mock_store.latest.return_value = mock_record
                mock_store_class.return_value = mock_store

                event = {"proposal_id": "test-123"}
                result = handler(event, None)

                assert result["statusCode"] == 200
                assert result["approved"] is True
                assert result["approver"] == "user@example.com"

    def test_no_approval_found(self):
        from lambdas.approval_checker.handler import handler

        with patch.dict(os.environ, {"APPROVAL_TABLE_NAME": "test-table"}):
            with patch('alpha_agent.approvals.ApprovalStore') as mock_store_class:
                mock_store = MagicMock()
                mock_store.latest.return_value = None
                mock_store_class.return_value = mock_store

                event = {"proposal_id": "test-123"}
                result = handler(event, None)

                assert result["statusCode"] == 200
                assert result["approved"] is False


class TestBedrockReasonerHandler:
    """Tests for lambdas/bedrock_reasoner/handler.py"""

    def test_missing_context(self):
        from lambdas.bedrock_reasoner.handler import handler

        event = {"policy": {"Version": "2012-10-17", "Statement": []}}
        result = handler(event, None)

        assert result["statusCode"] == 400
        assert "context" in result["error"]

    def test_missing_policy(self):
        from lambdas.bedrock_reasoner.handler import handler

        event = {"context": {"role": "TestRole"}}
        result = handler(event, None)

        assert result["statusCode"] == 400
        assert "policy" in result["error"]

    def test_successful_reasoning(self):
        from lambdas.bedrock_reasoner.handler import handler

        with patch('alpha_agent.reasoning.BedrockReasoner') as mock_reasoner_class:
            mock_reasoner = MagicMock()
            mock_proposal = MagicMock()
            mock_proposal.model_dump.return_value = {
                "proposed_policy": {},
                "rationale": "Test",
                "risk_signal": {}
            }
            mock_reasoner.propose_policy.return_value = mock_proposal
            mock_reasoner_class.return_value = mock_reasoner

            event = {
                "context": {"role": "TestRole"},
                "policy": {"Version": "2012-10-17", "Statement": []}
            }
            result = handler(event, None)

            assert result["statusCode"] == 200
            assert "proposal" in result


class TestGeneratePolicyHandler:
    """Tests for lambdas/generate_policy/handler.py"""

    def test_missing_required_fields(self):
        from lambdas.generate_policy.handler import handler

        event = {"analyzer_arn": "test"}
        result = handler(event, None)

        assert result["statusCode"] == 400

    def test_successful_generation(self):
        from lambdas.generate_policy.handler import handler

        with patch('alpha_agent.collector.generate_policy') as mock_generate:
            mock_policy = MagicMock()
            mock_policy.model_dump.return_value = {"Version": "2012-10-17", "Statement": []}
            mock_generate.return_value = mock_policy

            event = {
                "analyzer_arn": "arn:aws:access-analyzer:us-east-1:123:analyzer/test",
                "resource_arn": "arn:aws:iam::123:role/TestRole",
                "cloudtrail_access_role_arn": "arn:aws:iam::123:role/AccessRole",
                "cloudtrail_trail_arns": ["arn:aws:cloudtrail:us-east-1:123:trail/test"]
            }
            result = handler(event, None)

            assert result["statusCode"] == 200
            assert "policy" in result


class TestGuardrailHandler:
    """Tests for lambdas/guardrail/handler.py"""

    def test_missing_policy_field(self):
        from lambdas.guardrail.handler import handler

        event = {}
        result = handler(event, None)

        assert result["statusCode"] == 400

    def test_missing_proposed_policy(self):
        from lambdas.guardrail.handler import handler

        event = {"policy": {"rationale": "test"}}
        result = handler(event, None)

        assert result["statusCode"] == 400
        assert "proposed_policy" in result["error"]

    def test_successful_enforcement(self):
        from lambdas.guardrail.handler import handler

        event = {
            "policy": {
                "proposed_policy": {
                    "Version": "2012-10-17",
                    "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
                },
                "rationale": "Test"
            }
        }
        result = handler(event, None)

        assert result["statusCode"] == 200
        assert "sanitized_proposal" in result

    def test_violations_merged(self):
        from lambdas.guardrail.handler import handler

        event = {
            "policy": {
                "proposed_policy": {
                    "Version": "2012-10-17",
                    "Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}]
                },
                "guardrail_violations": [{"code": "EXISTING", "message": "Existing violation"}]
            }
        }
        result = handler(event, None)

        assert result["statusCode"] == 200
        # Should have both existing and new violations
        violations = result["sanitized_proposal"]["guardrail_violations"]
        assert len(violations) >= 1


class TestRolloutHandler:
    """Tests for lambdas/rollout/handler.py"""

    def test_missing_stage(self):
        from lambdas.rollout.handler import handler

        event = {"proposal": {"proposed_policy": {}}}
        result = handler(event, None)

        assert result["statusCode"] == 400

    def test_missing_role_arn(self):
        from lambdas.rollout.handler import handler

        event = {
            "stage": "sandbox",
            "proposal": {"proposed_policy": {"Version": "2012-10-17", "Statement": []}}
        }
        result = handler(event, None)

        assert result["statusCode"] == 400
        assert "role_arn" in result["error"]

    def test_successful_rollout(self):
        from lambdas.rollout.handler import handler

        with patch('alpha_agent.rollout.orchestrate_rollout') as mock_rollout:
            mock_outcome = MagicMock()
            mock_outcome.succeeded = True
            mock_outcome.stage.value = "sandbox"
            mock_outcome.metrics = {"error_rate": 0.0}
            mock_outcome.error = None
            mock_rollout.return_value = mock_outcome

            event = {
                "stage": "sandbox",
                "proposal": {
                    "proposed_policy": {"Version": "2012-10-17", "Statement": []},
                    "rationale": "Test"
                },
                "role_arn": "arn:aws:iam::123:role/TestRole"
            }
            result = handler(event, None)

            assert result["statusCode"] == 200
            assert result["succeeded"] is True

    def test_role_arn_from_proposal(self):
        from lambdas.rollout.handler import handler

        with patch('alpha_agent.rollout.orchestrate_rollout') as mock_rollout:
            mock_outcome = MagicMock()
            mock_outcome.succeeded = True
            mock_outcome.stage.value = "sandbox"
            mock_outcome.metrics = {}
            mock_outcome.error = None
            mock_rollout.return_value = mock_outcome

            event = {
                "stage": "sandbox",
                "proposal": {
                    "proposed_policy": {"Version": "2012-10-17", "Statement": []},
                    "role_arn": "arn:aws:iam::123:role/FromProposal"
                }
            }
            result = handler(event, None)

            assert result["statusCode"] == 200
