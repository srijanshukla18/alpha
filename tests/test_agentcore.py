"""
Tests for alpha_agent.agentcore module.

Tests AgentCore tools and tool definitions.
"""
import pytest
from unittest.mock import MagicMock, patch

from alpha_agent.agentcore import (
    AgentCoreTools,
    get_agentcore_tool_definitions,
)
from alpha_agent.models import PolicyDocument


class TestAgentCoreTools:
    """Tests for AgentCoreTools class."""

    def test_init_default(self):
        tools = AgentCoreTools()
        assert tools.reasoner is not None
        assert tools.approval_table is None
        assert tools.slack_webhook is None
        assert tools.github_token is None

    def test_init_with_config(self):
        mock_reasoner = MagicMock()
        tools = AgentCoreTools(
            reasoner=mock_reasoner,
            approval_table="test-table",
            slack_webhook="https://hooks.slack.com/test",
            github_token="ghp_test123"
        )
        assert tools.reasoner == mock_reasoner
        assert tools.approval_table == "test-table"
        assert tools.slack_webhook == "https://hooks.slack.com/test"
        assert tools.github_token == "ghp_test123"


class TestGenerateLeastPrivilegePolicy:
    """Tests for AgentCoreTools.generate_least_privilege_policy method."""

    def test_successful_generation(self):
        with patch('alpha_agent.agentcore.generate_policy') as mock_generate:
            mock_policy = PolicyDocument(
                statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
            )
            mock_generate.return_value = mock_policy

            tools = AgentCoreTools()
            result = tools.generate_least_privilege_policy(
                analyzer_arn="arn:aws:access-analyzer:us-east-1:123:analyzer/test",
                resource_arn="arn:aws:iam::123:role/TestRole",
                cloudtrail_access_role_arn="arn:aws:iam::123:role/AccessRole",
                cloudtrail_trail_arns=["arn:aws:cloudtrail:us-east-1:123:trail/test"]
            )

            assert result["status"] == "success"
            assert "policy" in result

    def test_generation_error(self):
        with patch('alpha_agent.agentcore.generate_policy') as mock_generate:
            mock_generate.side_effect = Exception("API error")

            tools = AgentCoreTools()
            result = tools.generate_least_privilege_policy(
                analyzer_arn="arn:aws:access-analyzer:us-east-1:123:analyzer/test",
                resource_arn="arn:aws:iam::123:role/TestRole",
                cloudtrail_access_role_arn="arn:aws:iam::123:role/AccessRole",
                cloudtrail_trail_arns=[]
            )

            assert result["status"] == "error"
            assert "error" in result


class TestReasonAboutPolicy:
    """Tests for AgentCoreTools.reason_about_policy method."""

    def test_successful_reasoning(self):
        mock_reasoner = MagicMock()
        mock_proposal = MagicMock()
        mock_proposal.model_dump.return_value = {
            "proposed_policy": {},
            "rationale": "Test",
            "risk_signal": {}
        }
        mock_reasoner.propose_policy.return_value = mock_proposal

        tools = AgentCoreTools(reasoner=mock_reasoner)
        result = tools.reason_about_policy(
            policy={"Version": "2012-10-17", "Statement": []},
            context={"role": "TestRole"}
        )

        assert result["status"] == "success"

    def test_reasoning_error(self):
        mock_reasoner = MagicMock()
        mock_reasoner.propose_policy.side_effect = Exception("Bedrock error")

        tools = AgentCoreTools(reasoner=mock_reasoner)
        result = tools.reason_about_policy(
            policy={"Version": "2012-10-17", "Statement": []},
            context={}
        )

        assert result["status"] == "error"


class TestEnforcePolicyGuardrails:
    """Tests for AgentCoreTools.enforce_policy_guardrails method."""

    def test_successful_enforcement(self):
        tools = AgentCoreTools()
        result = tools.enforce_policy_guardrails(
            policy={"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]},
            blocked_actions=["iam:PassRole"],
            required_conditions={},
            disallowed_services=[]
        )

        assert result["status"] == "success"
        assert "sanitized_policy" in result
        assert "violations" in result

    def test_with_violations(self):
        tools = AgentCoreTools()
        result = tools.enforce_policy_guardrails(
            policy={"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}]},
        )

        assert result["status"] == "success"
        assert len(result["violations"]) > 0


class TestComputePolicyChangeDiff:
    """Tests for AgentCoreTools.compute_policy_change_diff method."""

    def test_successful_diff(self):
        with patch('alpha_agent.agentcore.fetch_inline_policy') as mock_fetch:
            mock_fetch.return_value = PolicyDocument(
                statement=[{"Effect": "Allow", "Action": "*", "Resource": "*"}]
            )

            tools = AgentCoreTools()
            result = tools.compute_policy_change_diff(
                role_arn="arn:aws:iam::123:role/TestRole",
                existing_policy_name="CurrentPolicy",
                proposed_policy={"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]}
            )

            assert result["status"] == "success"
            assert "added_actions" in result
            assert "removed_actions" in result


class TestRequestHumanApproval:
    """Tests for AgentCoreTools.request_human_approval method."""

    def test_no_webhook_configured(self):
        tools = AgentCoreTools()
        result = tools.request_human_approval(
            proposal_id="test-123",
            proposal_summary="Test summary"
        )

        assert result["status"] == "error"
        assert "webhook" in result["error"].lower()

    def test_successful_request(self):
        with patch('alpha_agent.agentcore.send_slack_webhook') as mock_send:
            tools = AgentCoreTools(slack_webhook="https://hooks.slack.com/test")
            result = tools.request_human_approval(
                proposal_id="test-123",
                proposal_summary="Test summary",
                risk_level="high"
            )

            assert result["status"] == "success"
            assert result["approval_requested"] is True
            mock_send.assert_called_once()


class TestCheckApprovalStatus:
    """Tests for AgentCoreTools.check_approval_status method."""

    def test_no_table_configured(self):
        tools = AgentCoreTools()
        result = tools.check_approval_status(proposal_id="test-123")

        assert result["status"] == "error"
        assert "table" in result["error"].lower()

    def test_approved(self):
        with patch('alpha_agent.agentcore.ApprovalStore') as mock_store_class:
            mock_store = MagicMock()
            mock_record = MagicMock()
            mock_record.approved = True
            mock_record.approver = "user@example.com"
            mock_record.timestamp.isoformat.return_value = "2025-01-15T10:30:00Z"
            mock_store.latest.return_value = mock_record
            mock_store_class.return_value = mock_store

            tools = AgentCoreTools(approval_table="test-table")
            result = tools.check_approval_status(proposal_id="test-123")

            assert result["status"] == "success"
            assert result["approved"] is True

    def test_not_approved(self):
        with patch('alpha_agent.agentcore.ApprovalStore') as mock_store_class:
            mock_store = MagicMock()
            mock_store.latest.return_value = None
            mock_store_class.return_value = mock_store

            tools = AgentCoreTools(approval_table="test-table")
            result = tools.check_approval_status(proposal_id="test-123")

            assert result["status"] == "success"
            assert result["approved"] is False


class TestExecuteRolloutStage:
    """Tests for AgentCoreTools.execute_rollout_stage method."""

    def test_successful_rollout(self):
        with patch('alpha_agent.agentcore.orchestrate_rollout') as mock_rollout:
            mock_outcome = MagicMock()
            mock_outcome.succeeded = True
            mock_outcome.stage.value = "sandbox"
            mock_outcome.metrics = {"error_rate": 0.0}
            mock_outcome.error = None
            mock_rollout.return_value = mock_outcome

            tools = AgentCoreTools()
            result = tools.execute_rollout_stage(
                role_arn="arn:aws:iam::123:role/TestRole",
                policy={"Version": "2012-10-17", "Statement": []},
                stage="sandbox"
            )

            assert result["status"] == "success"
            assert result["succeeded"] is True


class TestCreateGithubPr:
    """Tests for AgentCoreTools.create_github_pr method."""

    def test_no_token_configured(self):
        tools = AgentCoreTools()
        result = tools.create_github_pr(
            repo="owner/repo",
            title="Test PR",
            body="Test body",
            head="feature-branch"
        )

        assert result["status"] == "error"
        assert "token" in result["error"].lower()

    def test_successful_pr(self):
        with patch('alpha_agent.agentcore.GitHubClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.create_pull_request.return_value = {
                "html_url": "https://github.com/owner/repo/pull/123",
                "number": 123
            }
            mock_client_class.return_value = mock_client

            tools = AgentCoreTools(github_token="ghp_test")
            result = tools.create_github_pr(
                repo="owner/repo",
                title="Test PR",
                body="Test body",
                head="feature-branch"
            )

            assert result["status"] == "success"
            assert result["pr_number"] == 123


class TestGetAgentcoreToolDefinitions:
    """Tests for get_agentcore_tool_definitions function."""

    def test_returns_list(self):
        definitions = get_agentcore_tool_definitions()
        assert isinstance(definitions, list)

    def test_all_tools_have_required_fields(self):
        definitions = get_agentcore_tool_definitions()
        for tool in definitions:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_expected_tools_present(self):
        definitions = get_agentcore_tool_definitions()
        tool_names = [t["name"] for t in definitions]

        assert "generate_least_privilege_policy" in tool_names
        assert "reason_about_policy" in tool_names
        assert "enforce_policy_guardrails" in tool_names
        assert "compute_policy_change_diff" in tool_names
        assert "request_human_approval" in tool_names
        assert "check_approval_status" in tool_names
        assert "execute_rollout_stage" in tool_names
        assert "create_github_pr" in tool_names

    def test_input_schema_structure(self):
        definitions = get_agentcore_tool_definitions()
        for tool in definitions:
            schema = tool["input_schema"]
            assert schema["type"] == "object"
            assert "properties" in schema
