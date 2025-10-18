from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Dict, List

from .approvals import ApprovalStore, ApprovalStoreError
from .collector import PolicyGenerationError, generate_policy
from .guardrails import enforce_guardrails
from .diff import compute_policy_diff, fetch_inline_policy
from .models import (
    Environment,
    PolicyGenerationRequest,
    PolicyProposal,
    RolloutStage,
    PolicyDiff,
)
from .notifications import NotificationPayload, NotificationError, send_slack_webhook
from .reasoning import BedrockReasoner, BedrockReasoningError
from .rollout import RolloutError, orchestrate_rollout
from .github import GitHubClient, GitHubError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


AGENTCORE_TOOLS: List[Dict] = [
    {
        "name": "iam_access_analyzer_policy_generator",
        "description": "Generate least-privilege IAM policies from CloudTrail activity.",
        "inputs": ["principalArn", "cloudtrailAccessRoleArn", "usagePeriodDays"],
        "outputs": ["policyDocument"],
    },
    {
        "name": "policy_guardrail_enforcer",
        "description": "Apply organization guardrails and identify violations in IAM policy documents.",
        "inputs": ["policyDocument"],
        "outputs": ["sanitizedPolicy", "violations"],
    },
    {
        "name": "rollout_stage_executor",
        "description": "Execute a rollout stage (sandbox/canary/target) for an IAM policy update.",
        "inputs": ["roleArn", "policyDocument", "stage"],
        "outputs": ["outcome"],
    },
]


def _build_context(args: argparse.Namespace) -> Dict:
    return {
        "role": args.resource_arn,
        "service_owner": args.service_owner,
        "environment": args.environment,
        "business_impact": args.business_impact,
        "notes": args.notes,
    }


def _merge_guardrail_violations(
    proposal: PolicyProposal,
    enforced_policy,
    extra_violations,
) -> PolicyProposal:
    merged = proposal.model_copy()
    merged.proposed_policy = enforced_policy
    merged.guardrail_violations.extend(extra_violations)
    return merged


def request_human_approval(
    proposal_id: str,
    proposal: PolicyProposal,
    approval_table: str,
    slack_webhook: str | None,
    policy_diff: PolicyDiff | None = None,
) -> bool:
    store = ApprovalStore(approval_table)
    try:
        latest = store.latest(proposal_id)
    except ApprovalStoreError as err:
        LOGGER.error("Approval lookup failed: %s", err)
        return False

    if latest and latest.approved:
        LOGGER.info("Proposal %s already approved by %s", proposal_id, latest.approver)
        return True

    if slack_webhook:
        metadata = {
            "Risk": f"{proposal.risk_signal.probability_of_break:.2%}",
            "Violations": str(len(proposal.guardrail_violations)),
        }
        if policy_diff:
            metadata["Summary"] = policy_diff.change_summary

        payload = NotificationPayload(
            channel="slack",
            message=(
                f"Approval required for IAM policy update `{proposal_id}`.\n"
                f"*Summary*: {proposal.rationale}"
            ),
            metadata=metadata,
        )
        try:
            send_slack_webhook(slack_webhook, payload)
        except NotificationError as err:
            LOGGER.warning("Failed to send Slack notification: %s", err)

    LOGGER.info(
        "Approval required for %s. Record approval in table %s to continue.",
        proposal_id,
        approval_table,
    )
    return False


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ALPHA IAM Hardening pipeline.")
    parser.add_argument("--analyzer-arn", required=True)
    parser.add_argument("--resource-arn", required=True)
    parser.add_argument("--cloudtrail-access-role-arn", required=True)
    parser.add_argument(
        "--cloudtrail-trail-arns",
        required=True,
        help="Comma-separated list of CloudTrail trail ARNs to source activity from.",
    )
    parser.add_argument("--usage-days", type=int, default=30)
    parser.add_argument(
        "--environment",
        type=lambda value: Environment(value),
        default=Environment.SANDBOX,
    )
    parser.add_argument("--service-owner", default="unknown")
    parser.add_argument("--business-impact", default="low")
    parser.add_argument("--notes", default="")
    parser.add_argument(
        "--baseline-policy-name",
        help="Existing inline policy name to diff against the proposal.",
    )
    parser.add_argument("--approval-table", help="DynamoDB table for approvals.")
    parser.add_argument("--slack-webhook", default=os.getenv("SLACK_WEBHOOK_URL"))
    parser.add_argument(
        "--rollout-stage",
        type=lambda value: RolloutStage(value),
        default=None,
        help="Set to sandbox/canary/target to execute a rollout stage.",
    )
    parser.add_argument(
        "--metrics-json",
        help="Path to JSON file containing dummy metrics for local runs.",
    )
    parser.add_argument(
        "--print-proposal",
        action="store_true",
        help="Print the proposal payload to stdout (for demo/debug).",
    )
    parser.add_argument(
        "--report-output",
        help="Path to write the proposal and diff report as JSON.",
    )
    parser.add_argument("--github-repo", help="owner/repo to open a pull request against.")
    parser.add_argument("--github-branch", help="Branch name containing staged policy changes.")
    parser.add_argument("--github-base", default="main", help="Base branch for the pull request.")
    parser.add_argument("--github-token", help="Personal access token for GitHub API calls.")
    parser.add_argument(
        "--github-pr-title",
        default="ALPHA Least-Privilege Policy Update",
        help="Title to use for the generated pull request.",
    )
    parser.add_argument(
        "--github-draft",
        action="store_true",
        help="Open the pull request as a draft.",
    )
    return parser.parse_args(argv)


def _load_metrics(path: str | None) -> Dict[str, float]:
    if not path:
        return {"error_rate": 0.0}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def run(argv: List[str]) -> int:
    args = parse_args(argv)
    request = PolicyGenerationRequest(
        analyzer_arn=args.analyzer_arn,
        resource_arn=args.resource_arn,
        cloudtrail_access_role_arn=args.cloudtrail_access_role_arn,
        cloudtrail_trail_arns=[arn.strip() for arn in args.cloudtrail_trail_arns.split(",") if arn.strip()],
        usage_period_days=args.usage_days,
    )

    try:
        generated_policy = generate_policy(request)
    except PolicyGenerationError as err:
        LOGGER.error("Policy generation failed: %s", err)
        return 1

    context = _build_context(args)
    reasoner = BedrockReasoner()
    try:
        proposal = reasoner.propose_policy(context, generated_policy)
    except BedrockReasoningError as err:
        LOGGER.error("Bedrock reasoning failed: %s", err)
        return 1

    sanitized_policy, guardrail_violations = enforce_guardrails(
        proposal.proposed_policy,
        blocked_actions=["iam:PassRole"],
        required_conditions={"StringEquals": {"aws:RequestedRegion": "us-east-1"}},
        disallowed_services=["iam"],
    )
    proposal = _merge_guardrail_violations(proposal, sanitized_policy, guardrail_violations)

    existing_policy = None
    policy_diff = None
    if args.baseline_policy_name:
        existing_policy = fetch_inline_policy(args.resource_arn, args.baseline_policy_name)
        policy_diff = compute_policy_diff(existing_policy, proposal.proposed_policy)

    if args.report_output:
        report_payload = {
            "context": context,
            "proposal": proposal.model_dump(mode="json", by_alias=True),
            "diff": policy_diff.model_dump(mode="json", by_alias=True) if policy_diff else None,
        }
        with open(args.report_output, "w", encoding="utf-8") as handle:
            json.dump(report_payload, handle, indent=2)
        LOGGER.info("Report written to %s", args.report_output)

    if (
        args.github_repo
        and args.github_branch
        and args.github_token
        and policy_diff
    ):
        summary_lines = ["## Summary", f"- {policy_diff.change_summary}"]
        if policy_diff.added_actions:
            summary_lines.append("\n### Added actions")
            summary_lines.extend(f"- `{action}`" for action in policy_diff.added_actions)
        if policy_diff.removed_actions:
            summary_lines.append("\n### Removed actions")
            summary_lines.extend(f"- `{action}`" for action in policy_diff.removed_actions)
        summary_lines.append("\n```json")
        summary_lines.append(json.dumps(proposal.proposed_policy.model_dump(by_alias=True), indent=2))
        summary_lines.append("```")
        pr_body = "\n".join(summary_lines)

        try:
            gh_client = GitHubClient(token=args.github_token)
            gh_client.create_pull_request(
                repo=args.github_repo,
                title=args.github_pr_title,
                body=pr_body,
                head=args.github_branch,
                base=args.github_base,
                draft=args.github_draft,
            )
        except GitHubError as err:
            LOGGER.error("Failed to create GitHub PR: %s", err)

    if args.print_proposal:
        printable = {
            "proposal": proposal.model_dump(mode="json", by_alias=True),
            "diff": policy_diff.model_dump(mode="json", by_alias=True) if policy_diff else None,
        }
        print(json.dumps(printable, indent=2))

    if args.approval_table:
        if not request_human_approval(
            proposal_id=args.resource_arn,
            proposal=proposal,
            approval_table=args.approval_table,
            slack_webhook=args.slack_webhook,
            policy_diff=policy_diff,
        ):
            return 2

    if args.rollout_stage:
        metrics = _load_metrics(args.metrics_json)

        def metrics_collector():
            return metrics

        try:
            outcome = orchestrate_rollout(
                role_arn=args.resource_arn,
                policy_document=proposal.proposed_policy,
                stage=args.rollout_stage,
                metrics_collector=metrics_collector,
                description=proposal.rationale,
            )
        except RolloutError as err:
            LOGGER.error("Rollout execution failed: %s", err)
            return 1

        LOGGER.info("Rollout outcome: %s", outcome.model_dump())

    return 0


def main() -> None:
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
