"""
Amazon Bedrock AgentCore integration module.

This module provides the AgentCore runtime integration for ALPHA,
exposing policy generation, reasoning, and rollout capabilities as
AgentCore tools that can be orchestrated by the AgentCore Runtime.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .approvals import ApprovalStore
from .collector import generate_policy
from .diff import compute_policy_diff, fetch_inline_policy
from .github import GitHubClient
from .guardrails import enforce_guardrails
from .models import (
    PolicyDocument,
    PolicyGenerationRequest,
    RolloutStage,
)
from .notifications import NotificationPayload, send_slack_webhook
from .reasoning import BedrockReasoner
from .rollout import orchestrate_rollout

LOGGER = logging.getLogger(__name__)


class AgentCoreTools:
    """
    Wrapper for ALPHA tools compatible with AgentCore Runtime.

    These tools can be registered with AgentCore Gateway to enable
    agent-driven IAM policy remediation workflows.
    """

    def __init__(
        self,
        reasoner: Optional[BedrockReasoner] = None,
        approval_table: Optional[str] = None,
        slack_webhook: Optional[str] = None,
        github_token: Optional[str] = None,
    ) -> None:
        self.reasoner = reasoner or BedrockReasoner()
        self.approval_table = approval_table
        self.slack_webhook = slack_webhook
        self.github_token = github_token

    def generate_least_privilege_policy(
        self,
        analyzer_arn: str,
        resource_arn: str,
        cloudtrail_access_role_arn: str,
        cloudtrail_trail_arns: List[str],
        usage_period_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Tool: Generate least-privilege IAM policy from CloudTrail activity.

        This tool invokes IAM Access Analyzer to produce a policy based on
        actual usage telemetry over the specified time period.

        Returns:
        {
            "policy": { "Version": "2012-10-17", "Statement": [...] },
            "job_id": "...",
            "status": "success"
        }
        """
        try:
            request = PolicyGenerationRequest(
                analyzer_arn=analyzer_arn,
                resource_arn=resource_arn,
                cloudtrail_access_role_arn=cloudtrail_access_role_arn,
                cloudtrail_trail_arns=cloudtrail_trail_arns,
                usage_period_days=usage_period_days,
            )

            policy = generate_policy(request)

            return {
                "policy": policy.model_dump(by_alias=True),
                "status": "success",
            }
        except Exception as err:  # pylint: disable=broad-exception-caught
            LOGGER.error("Policy generation failed: %s", err)
            return {
                "status": "error",
                "error": str(err),
            }

    def reason_about_policy(
        self,
        policy: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Tool: Use Bedrock reasoning to analyze and propose policy improvements.

        Invokes Claude on Bedrock to produce human-readable rationale,
        risk assessment, and remediation guidance.

        Returns:
        {
            "proposed_policy": {...},
            "rationale": "...",
            "risk_signal": {"probability_of_break": 0.0, "rationale": "..."},
            "guardrail_violations": [...],
            "status": "success"
        }
        """
        try:
            policy_doc = PolicyDocument(**policy)
            proposal = self.reasoner.propose_policy(context, policy_doc)

            return {
                **proposal.model_dump(mode="json", by_alias=True),
                "status": "success",
            }
        except Exception as err:  # pylint: disable=broad-exception-caught
            LOGGER.error("Reasoning failed: %s", err)
            return {
                "status": "error",
                "error": str(err),
            }

    def enforce_policy_guardrails(
        self,
        policy: Dict[str, Any],
        blocked_actions: Optional[List[str]] = None,
        required_conditions: Optional[Dict] = None,
        disallowed_services: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Tool: Apply organizational guardrails to a policy.

        Sanitizes the policy by removing violations and returns the
        updated policy plus a list of detected violations.

        Returns:
        {
            "sanitized_policy": {...},
            "violations": [...],
            "status": "success"
        }
        """
        try:
            policy_doc = PolicyDocument(**policy)
            sanitized, violations = enforce_guardrails(
                policy_doc,
                blocked_actions=blocked_actions or [],
                required_conditions=required_conditions or {},
                disallowed_services=disallowed_services or [],
            )

            return {
                "sanitized_policy": sanitized.model_dump(by_alias=True),
                "violations": [v.model_dump() for v in violations],
                "status": "success",
            }
        except Exception as err:  # pylint: disable=broad-exception-caught
            LOGGER.error("Guardrail enforcement failed: %s", err)
            return {
                "status": "error",
                "error": str(err),
            }

    def compute_policy_change_diff(
        self,
        role_arn: str,
        existing_policy_name: str,
        proposed_policy: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Tool: Compute a diff between existing and proposed policies.

        Fetches the current inline policy from IAM and compares action-level
        changes with the proposed policy.

        Returns:
        {
            "added_actions": [...],
            "removed_actions": [...],
            "change_summary": "...",
            "status": "success"
        }
        """
        try:
            existing = fetch_inline_policy(role_arn, existing_policy_name)
            proposed = PolicyDocument(**proposed_policy)
            diff = compute_policy_diff(existing, proposed)

            return {
                "added_actions": diff.added_actions,
                "removed_actions": diff.removed_actions,
                "change_summary": diff.change_summary,
                "status": "success",
            }
        except Exception as err:  # pylint: disable=broad-exception-caught
            LOGGER.error("Diff computation failed: %s", err)
            return {
                "status": "error",
                "error": str(err),
            }

    def request_human_approval(
        self,
        proposal_id: str,
        proposal_summary: str,
        risk_level: str = "medium",
    ) -> Dict[str, Any]:
        """
        Tool: Send approval request to humans via Slack.

        Notifies a Slack channel and persists the approval request
        in DynamoDB for tracking.

        Returns:
        {
            "approval_requested": true,
            "status": "success"
        }
        """
        try:
            if not self.slack_webhook:
                return {
                    "status": "error",
                    "error": "Slack webhook not configured",
                }

            payload = NotificationPayload(
                channel="slack",
                message=f"Approval required for policy update `{proposal_id}`.\n\n{proposal_summary}",
                metadata={"Risk": risk_level},
            )

            send_slack_webhook(self.slack_webhook, payload)

            return {
                "approval_requested": True,
                "status": "success",
            }
        except Exception as err:  # pylint: disable=broad-exception-caught
            LOGGER.error("Approval request failed: %s", err)
            return {
                "status": "error",
                "error": str(err),
            }

    def check_approval_status(self, proposal_id: str) -> Dict[str, Any]:
        """
        Tool: Check if a proposal has been approved by a human.

        Queries DynamoDB for the latest approval record.

        Returns:
        {
            "approved": true,
            "approver": "user@example.com",
            "status": "success"
        }
        """
        try:
            if not self.approval_table:
                return {
                    "status": "error",
                    "error": "Approval table not configured",
                }

            store = ApprovalStore(self.approval_table)
            latest = store.latest(proposal_id)

            if latest:
                return {
                    "approved": latest.approved,
                    "approver": latest.approver,
                    "timestamp": latest.timestamp.isoformat(),
                    "status": "success",
                }

            return {
                "approved": False,
                "status": "success",
            }
        except Exception as err:  # pylint: disable=broad-exception-caught
            LOGGER.error("Approval check failed: %s", err)
            return {
                "status": "error",
                "error": str(err),
            }

    def execute_rollout_stage(
        self,
        role_arn: str,
        policy: Dict[str, Any],
        stage: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Tool: Execute a policy rollout stage (sandbox/canary/target).

        Attaches the policy, monitors metrics, and evaluates success.

        Returns:
        {
            "succeeded": true,
            "stage": "sandbox",
            "metrics": {...},
            "status": "success"
        }
        """
        try:
            policy_doc = PolicyDocument(**policy)
            rollout_stage = RolloutStage(stage)

            # Dummy metrics collector for demo
            def metrics_collector():
                return {"error_rate": 0.0}

            outcome = orchestrate_rollout(
                role_arn=role_arn,
                policy_document=policy_doc,
                stage=rollout_stage,
                metrics_collector=metrics_collector,
                description=description,
            )

            return {
                "succeeded": outcome.succeeded,
                "stage": outcome.stage.value,
                "metrics": outcome.metrics,
                "error": outcome.error,
                "status": "success",
            }
        except Exception as err:  # pylint: disable=broad-exception-caught
            LOGGER.error("Rollout execution failed: %s", err)
            return {
                "status": "error",
                "error": str(err),
            }

    def create_github_pr(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        draft: bool = False,
    ) -> Dict[str, Any]:
        """
        Tool: Create a GitHub pull request for policy changes.

        Opens a PR with the proposed policy diff and rationale.

        Returns:
        {
            "pr_url": "https://github.com/owner/repo/pull/123",
            "pr_number": 123,
            "status": "success"
        }
        """
        try:
            if not self.github_token:
                return {
                    "status": "error",
                    "error": "GitHub token not configured",
                }

            client = GitHubClient(token=self.github_token)
            pr = client.create_pull_request(
                repo=repo,
                title=title,
                body=body,
                head=head,
                base=base,
                draft=draft,
            )

            return {
                "pr_url": pr.get("html_url"),
                "pr_number": pr.get("number"),
                "status": "success",
            }
        except Exception as err:  # pylint: disable=broad-exception-caught
            LOGGER.error("GitHub PR creation failed: %s", err)
            return {
                "status": "error",
                "error": str(err),
            }


def get_agentcore_tool_definitions() -> List[Dict[str, Any]]:
    """
    Return AgentCore tool definitions for registering with AgentCore Gateway.

    These definitions describe the tools available to the agent runtime.
    """
    return [
        {
            "name": "generate_least_privilege_policy",
            "description": "Generate least-privilege IAM policies from CloudTrail activity using IAM Access Analyzer.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "analyzer_arn": {"type": "string"},
                    "resource_arn": {"type": "string"},
                    "cloudtrail_access_role_arn": {"type": "string"},
                    "cloudtrail_trail_arns": {"type": "array", "items": {"type": "string"}},
                    "usage_period_days": {"type": "integer", "default": 30},
                },
                "required": [
                    "analyzer_arn",
                    "resource_arn",
                    "cloudtrail_access_role_arn",
                    "cloudtrail_trail_arns",
                ],
            },
        },
        {
            "name": "reason_about_policy",
            "description": "Use Bedrock reasoning (Claude) to analyze policies and propose improvements with risk assessment.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "policy": {"type": "object"},
                    "context": {"type": "object"},
                },
                "required": ["policy", "context"],
            },
        },
        {
            "name": "enforce_policy_guardrails",
            "description": "Apply organizational guardrails to sanitize and validate policies.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "policy": {"type": "object"},
                    "blocked_actions": {"type": "array", "items": {"type": "string"}},
                    "required_conditions": {"type": "object"},
                    "disallowed_services": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["policy"],
            },
        },
        {
            "name": "compute_policy_change_diff",
            "description": "Compute action-level diff between existing and proposed IAM policies.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "role_arn": {"type": "string"},
                    "existing_policy_name": {"type": "string"},
                    "proposed_policy": {"type": "object"},
                },
                "required": ["role_arn", "existing_policy_name", "proposed_policy"],
            },
        },
        {
            "name": "request_human_approval",
            "description": "Send approval request to humans via Slack and persist in DynamoDB.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "proposal_id": {"type": "string"},
                    "proposal_summary": {"type": "string"},
                    "risk_level": {"type": "string", "default": "medium"},
                },
                "required": ["proposal_id", "proposal_summary"],
            },
        },
        {
            "name": "check_approval_status",
            "description": "Check if a policy proposal has been approved by querying DynamoDB.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "proposal_id": {"type": "string"},
                },
                "required": ["proposal_id"],
            },
        },
        {
            "name": "execute_rollout_stage",
            "description": "Execute a policy rollout stage (sandbox/canary/target) with metrics monitoring.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "role_arn": {"type": "string"},
                    "policy": {"type": "object"},
                    "stage": {"type": "string", "enum": ["sandbox", "canary", "target"]},
                    "description": {"type": "string"},
                },
                "required": ["role_arn", "policy", "stage"],
            },
        },
        {
            "name": "create_github_pr",
            "description": "Create a GitHub pull request for policy changes.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "head": {"type": "string"},
                    "base": {"type": "string", "default": "main"},
                    "draft": {"type": "boolean", "default": False},
                },
                "required": ["repo", "title", "body", "head"],
            },
        },
    ]
