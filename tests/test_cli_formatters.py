"""
Tests for alpha_agent.cli.formatters module.

Tests output formatting functions for terminal, PR, CloudFormation, Terraform.
"""
import pytest
import json

from alpha_agent.cli.formatters import (
    Colors,
    format_terminal_summary,
    format_pr_comment,
    format_cloudformation_patch,
    format_terraform_patch,
    format_json_proposal,
)
from alpha_agent.models import (
    PolicyDocument,
    PolicyProposal,
    PolicyDiff,
    RiskSignal,
    GuardrailViolation,
)


class TestColors:
    """Tests for Colors class."""

    def test_ansi_codes_defined(self):
        assert Colors.GREEN.startswith("\033[")
        assert Colors.RED.startswith("\033[")
        assert Colors.YELLOW.startswith("\033[")
        assert Colors.END.startswith("\033[")

    def test_end_resets_color(self):
        assert Colors.END == "\033[0m"


class TestFormatTerminalSummary:
    """Tests for format_terminal_summary function."""

    def test_basic_summary(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test rationale",
            risk_signal=RiskSignal(probability_of_break=0.05, rationale="Low risk")
        )

        output = format_terminal_summary(proposal)
        assert "ALPHA" in output
        assert "Risk Assessment" in output
        assert "5.0%" in output

    def test_with_diff(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal(probability_of_break=0.05)
        )
        diff = PolicyDiff(
            proposed_policy=policy,
            added_actions=["s3:GetObject", "s3:PutObject"],
            removed_actions=["s3:DeleteObject"]
        )

        output = format_terminal_summary(proposal, diff)
        assert "Added" in output
        assert "Removed" in output

    def test_with_guardrail_violations(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal(probability_of_break=0.05),
            guardrail_violations=[
                GuardrailViolation(code="WILDCARD", message="Wildcard detected")
            ]
        )

        output = format_terminal_summary(proposal)
        assert "Guardrail" in output
        assert "WILDCARD" in output

    def test_with_remediation_notes(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal(probability_of_break=0.05),
            remediation_notes=["Check bucket policy", "Monitor errors"]
        )

        output = format_terminal_summary(proposal)
        assert "Remediation" in output
        assert "bucket policy" in output

    def test_risk_color_green_low(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal(probability_of_break=0.05)
        )

        output = format_terminal_summary(proposal)
        assert Colors.GREEN in output

    def test_risk_color_red_high(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal(probability_of_break=0.30)
        )

        output = format_terminal_summary(proposal)
        assert Colors.RED in output


class TestFormatPrComment:
    """Tests for format_pr_comment function."""

    def test_basic_pr_comment(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal(probability_of_break=0.05)
        )
        diff = PolicyDiff(
            proposed_policy=policy,
            added_actions=["s3:GetObject"],
            removed_actions=["s3:*"]
        )

        output = format_pr_comment("TestRole", proposal, diff)
        assert "ALPHA" in output
        assert "TestRole" in output
        assert "Risk Assessment" in output

    def test_markdown_format(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal(probability_of_break=0.05)
        )
        diff = PolicyDiff(
            proposed_policy=policy,
            added_actions=["s3:GetObject"],
            removed_actions=[]
        )

        output = format_pr_comment("TestRole", proposal, diff)
        assert "##" in output  # Headers
        assert "```json" in output  # Code block
        assert "</details>" in output  # Collapsible section

    def test_shows_added_actions(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal(probability_of_break=0.05)
        )
        diff = PolicyDiff(
            proposed_policy=policy,
            added_actions=["s3:GetObject", "s3:PutObject"],
            removed_actions=[]
        )

        output = format_pr_comment("TestRole", proposal, diff)
        assert "Added Actions" in output
        assert "`s3:GetObject`" in output

    def test_shows_removed_actions(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal(probability_of_break=0.05)
        )
        diff = PolicyDiff(
            proposed_policy=policy,
            added_actions=[],
            removed_actions=["s3:DeleteObject"]
        )

        output = format_pr_comment("TestRole", proposal, diff)
        assert "Removed Actions" in output
        assert "`s3:DeleteObject`" in output


class TestFormatCloudformationPatch:
    """Tests for format_cloudformation_patch function."""

    def test_basic_patch(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal()
        )

        output = format_cloudformation_patch("MyRole", proposal)
        assert "MyRole" in output
        assert "AWS::IAM::Role" in output
        assert "ALPHALeastPrivilege" in output

    def test_yaml_structure(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal()
        )

        output = format_cloudformation_patch("MyRole", proposal)
        assert "Type:" in output
        assert "Properties:" in output
        assert "Policies:" in output

    def test_includes_version(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal()
        )

        output = format_cloudformation_patch("MyRole", proposal)
        assert "2012-10-17" in output


class TestFormatTerraformPatch:
    """Tests for format_terraform_patch function."""

    def test_basic_patch(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal()
        )

        output = format_terraform_patch("my_role", proposal)
        assert "my_role" in output
        assert "aws_iam_role_policy" in output
        assert "ALPHALeastPrivilege" in output

    def test_hcl_structure(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal()
        )

        output = format_terraform_patch("my_role", proposal)
        assert "resource" in output
        assert "jsonencode" in output
        assert "policy =" in output

    def test_includes_json_policy(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal()
        )

        output = format_terraform_patch("my_role", proposal)
        assert "Version" in output
        assert "Statement" in output


class TestFormatJsonProposal:
    """Tests for format_json_proposal function."""

    def test_basic_output(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal()
        )

        output = format_json_proposal(proposal)
        assert "version" in output
        assert "proposal" in output

    def test_with_diff(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal()
        )
        diff = PolicyDiff(
            proposed_policy=policy,
            added_actions=["s3:GetObject"],
            removed_actions=[]
        )

        output = format_json_proposal(proposal, diff)
        assert "diff" in output

    def test_with_metadata(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal()
        )

        output = format_json_proposal(
            proposal,
            metadata={"role_arn": "test", "usage_days": 30}
        )
        assert "metadata" in output
        assert output["metadata"]["role_arn"] == "test"

    def test_serializable(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        )
        proposal = PolicyProposal(
            proposed_policy=policy,
            rationale="Test",
            risk_signal=RiskSignal(probability_of_break=0.05)
        )
        diff = PolicyDiff(
            proposed_policy=policy,
            added_actions=["s3:GetObject"],
            removed_actions=[]
        )

        output = format_json_proposal(proposal, diff, {"key": "value"})
        # Should be JSON serializable
        json_str = json.dumps(output)
        assert len(json_str) > 0
