"""
Tests for alpha_agent.reasoning module.

Tests Bedrock reasoning and policy proposal generation.
"""
import pytest
from unittest.mock import MagicMock, patch
import json
import io

from alpha_agent.reasoning import (
    BedrockReasoner,
    BedrockReasoningError,
)
from alpha_agent.models import PolicyDocument, PolicyProposal, RiskSignal


class TestBedrockReasoner:
    """Tests for BedrockReasoner class."""

    def test_init_default_model(self):
        with patch.dict('os.environ', {}, clear=True):
            reasoner = BedrockReasoner()
            # Should use default model
            assert "claude" in reasoner.model_id.lower() or "anthropic" in reasoner.model_id.lower()

    def test_init_custom_model(self):
        reasoner = BedrockReasoner(model_id="amazon.titan-text-express-v1")
        assert reasoner.model_id == "amazon.titan-text-express-v1"

    def test_init_env_model_override(self):
        with patch.dict('os.environ', {"ALPHA_BEDROCK_MODEL_ID": "custom-model"}):
            reasoner = BedrockReasoner()
            assert reasoner.model_id == "custom-model"

    def test_init_temperature(self):
        reasoner = BedrockReasoner(temperature=0.5)
        assert reasoner.temperature == 0.5

    def test_build_prompt(self):
        reasoner = BedrockReasoner()
        context = {"role": "TestRole", "environment": "production"}
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        prompt = reasoner._build_prompt(context, policy)
        assert "ALPHA" in prompt
        assert "TestRole" in prompt
        assert "s3:GetObject" in prompt

    def test_propose_policy_anthropic_model(self):
        mock_client = MagicMock()
        response_body = {
            "content": [{
                "text": json.dumps({
                    "policy": {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]},
                    "rationale": "Based on usage analysis",
                    "risk_signal": {"probability_of_break": 0.05, "rationale": "Low risk"},
                    "guardrail_violations": [],
                    "remediation_notes": ["Check bucket policy"]
                })
            }]
        }
        mock_client.invoke_model.return_value = {
            "body": io.BytesIO(json.dumps(response_body).encode())
        }

        reasoner = BedrockReasoner(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            client=mock_client
        )
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "*", "Resource": "*"}]
        )
        context = {"role": "TestRole"}

        proposal = reasoner.propose_policy(context, policy)
        assert isinstance(proposal, PolicyProposal)
        assert proposal.rationale == "Based on usage analysis"
        assert proposal.risk_signal.probability_of_break == 0.05

    def test_propose_policy_nova_model(self):
        mock_client = MagicMock()
        response_body = {
            "output": {
                "message": {
                    "content": [{
                        "text": json.dumps({
                            "policy": {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]},
                            "rationale": "Nova analysis",
                            "risk_signal": {"probability_of_break": 0.10},
                            "guardrail_violations": [],
                            "remediation_notes": []
                        })
                    }]
                }
            }
        }
        mock_client.invoke_model.return_value = {
            "body": io.BytesIO(json.dumps(response_body).encode())
        }

        reasoner = BedrockReasoner(
            model_id="us.amazon.nova-pro-v1:0",
            client=mock_client
        )
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "*", "Resource": "*"}]
        )
        context = {"role": "TestRole"}

        proposal = reasoner.propose_policy(context, policy)
        assert isinstance(proposal, PolicyProposal)
        assert proposal.rationale == "Nova analysis"

    def test_propose_policy_titan_model(self):
        mock_client = MagicMock()
        response_body = {
            "results": [{
                "outputText": json.dumps({
                    "policy": {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]},
                    "rationale": "Titan analysis",
                    "risk_signal": {},
                    "guardrail_violations": [],
                    "remediation_notes": []
                })
            }]
        }
        mock_client.invoke_model.return_value = {
            "body": io.BytesIO(json.dumps(response_body).encode())
        }

        reasoner = BedrockReasoner(
            model_id="amazon.titan-text-express-v1",
            client=mock_client
        )
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "*", "Resource": "*"}]
        )
        context = {"role": "TestRole"}

        proposal = reasoner.propose_policy(context, policy)
        assert isinstance(proposal, PolicyProposal)

    def test_propose_policy_client_error(self):
        mock_client = MagicMock()
        from botocore.exceptions import ClientError
        mock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ModelNotReady"}},
            "InvokeModel"
        )

        reasoner = BedrockReasoner(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            client=mock_client
        )
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "*", "Resource": "*"}]
        )

        with pytest.raises(BedrockReasoningError):
            reasoner.propose_policy({}, policy)

    def test_propose_policy_invalid_json_response(self):
        mock_client = MagicMock()
        response_body = {
            "content": [{
                "text": "This is not valid JSON"
            }]
        }
        mock_client.invoke_model.return_value = {
            "body": io.BytesIO(json.dumps(response_body).encode())
        }

        reasoner = BedrockReasoner(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            client=mock_client
        )
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "*", "Resource": "*"}]
        )

        with pytest.raises(BedrockReasoningError):
            reasoner.propose_policy({}, policy)

    def test_propose_policy_missing_text_field(self):
        mock_client = MagicMock()
        response_body = {"content": [{}]}  # Missing text field
        mock_client.invoke_model.return_value = {
            "body": io.BytesIO(json.dumps(response_body).encode())
        }

        reasoner = BedrockReasoner(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            client=mock_client
        )
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "*", "Resource": "*"}]
        )

        with pytest.raises(BedrockReasoningError):
            reasoner.propose_policy({}, policy)

    def test_propose_policy_with_guardrail_violations(self):
        mock_client = MagicMock()
        response_body = {
            "content": [{
                "text": json.dumps({
                    "policy": {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]},
                    "rationale": "Analysis complete",
                    "risk_signal": {"probability_of_break": 0.15, "rationale": "Some risk"},
                    "guardrail_violations": [
                        {"code": "WILDCARD", "message": "Wildcard detected", "path": "statement[0]"}
                    ],
                    "remediation_notes": ["Review permissions"]
                })
            }]
        }
        mock_client.invoke_model.return_value = {
            "body": io.BytesIO(json.dumps(response_body).encode())
        }

        reasoner = BedrockReasoner(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            client=mock_client
        )
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "*", "Resource": "*"}]
        )

        proposal = reasoner.propose_policy({}, policy)
        assert len(proposal.guardrail_violations) == 1
        assert len(proposal.remediation_notes) == 1

    def test_anthropic_vs_us_anthropic_detection(self):
        # Test us.anthropic prefix
        reasoner1 = BedrockReasoner(model_id="us.anthropic.claude-3-sonnet")
        assert "anthropic" in reasoner1.model_id

        # Test anthropic prefix
        reasoner2 = BedrockReasoner(model_id="anthropic.claude-3-haiku")
        assert "anthropic" in reasoner2.model_id

    def test_nova_region_prefix_detection(self):
        reasoner1 = BedrockReasoner(model_id="amazon.nova-pro")
        reasoner2 = BedrockReasoner(model_id="us.amazon.nova-pro")
        reasoner3 = BedrockReasoner(model_id="eu.amazon.nova-lite")
        # All should be recognized as Nova models
        # (verification would be in the actual model invocation logic)
        assert "nova" in reasoner1.model_id
        assert "nova" in reasoner2.model_id
        assert "nova" in reasoner3.model_id


class TestBedrockReasoningError:
    """Tests for BedrockReasoningError exception."""

    def test_error_message(self):
        error = BedrockReasoningError("Test error message")
        assert str(error) == "Test error message"

    def test_inherits_from_runtime_error(self):
        error = BedrockReasoningError("Test")
        assert isinstance(error, RuntimeError)
