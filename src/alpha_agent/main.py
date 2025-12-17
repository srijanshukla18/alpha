"""
ALPHA CLI - Autonomous Least-Privilege Hardening Agent

Command-line interface for IAM policy analysis and hardening.

Commands:
  analyze  - Analyze IAM role usage and generate least-privilege policy
  propose  - Create GitHub PR with policy proposal
  apply    - Execute staged rollout via Step Functions

Examples:
  # Analyze a role (mock mode for demo)
  alpha analyze --role-arn arn:aws:iam::123:role/ci-runner --mock-mode

  # Analyze with real AWS APIs
  alpha analyze --role-arn arn:aws:iam::123:role/ci-runner --output proposal.json

  # Create GitHub PR
  alpha propose --repo org/infra --branch harden/ci-runner --input proposal.json

  # Apply with staged rollout
  alpha apply --state-machine-arn arn:aws:states:... --proposal proposal.json --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys

from alpha_agent.cli import EXIT_CODE_DESCRIPTIONS
from alpha_agent.cli.analyze import run_analyze
from alpha_agent.cli.propose import run_propose
from alpha_agent.cli.apply import run_apply
from alpha_agent.cli.diff import run_diff
from alpha_agent.cli.status import run_status
from alpha_agent.cli.rollback import run_rollback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="alpha",
        description="ALPHA - Autonomous Least-Privilege Hardening Agent",
        epilog="See https://github.com/your-org/alpha for full documentation",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to run")

    # ===== ANALYZE COMMAND =====
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze IAM role usage and generate least-privilege policy",
    )

    analyze_parser.add_argument(
        "--role-arn",
        required=True,
        help="IAM role ARN to analyze (e.g., arn:aws:iam::123:role/MyRole)",
    )

    analyze_parser.add_argument(
        "--usage-days",
        type=int,
        default=30,
        help="Number of days of CloudTrail activity to analyze (default: 30)",
    )

    analyze_parser.add_argument(
        "--output",
        help="Path to save proposal JSON (e.g., proposal.json)",
    )

    analyze_parser.add_argument(
        "--guardrails",
        choices=["none", "sandbox", "prod"],
        default="prod",
        help="Guardrail preset to apply (default: prod)",
    )

    analyze_parser.add_argument(
        "--baseline-policy-name",
        help="Existing inline policy name to diff against",
    )

    analyze_parser.add_argument(
        "--exclude-services",
        help="Comma-separated list of services to exclude (e.g., ec2,iam)",
    )

    analyze_parser.add_argument(
        "--suppress-actions",
        help="Comma-separated list of actions to suppress (e.g., s3:DeleteBucket)",
    )

    analyze_parser.add_argument(
        "--mock-mode",
        action="store_true",
        help="Use deterministic mock data for offline demo (no AWS calls)",
    )

    analyze_parser.add_argument(
        "--output-cloudformation",
        help="Path to save CloudFormation YAML patch (e.g., cfn-patch.yml)",
    )

    analyze_parser.add_argument(
        "--output-terraform",
        help="Path to save Terraform HCL patch (e.g., tf-patch.tf)",
    )

    analyze_parser.add_argument(
        "--timeout-seconds",
        type=int,
        help="Max seconds to wait for Access Analyzer job (default: 1800 or ALPHA_ANALYZE_TIMEOUT_SECONDS)",
    )

    analyze_parser.add_argument(
        "--fast",
        dest="fast",
        action="store_true",
        default=True,
        help="Fast mode (default): use CloudTrail Event History (no Access Analyzer)",
    )
    analyze_parser.add_argument(
        "--no-fast",
        dest="fast",
        action="store_false",
        help="Disable fast mode; use Access Analyzer",
    )

    analyze_parser.add_argument(
        "--bedrock-model",
        dest="bedrock_model",
        help="Override Bedrock model ID (e.g., us.amazon.nova-pro-v1:0). Defaults to ALPHA_BEDROCK_MODEL_ID or Anthropic Sonnet.",
    )

    # ===== PROPOSE COMMAND =====
    propose_parser = subparsers.add_parser(
        "propose",
        help="Create GitHub pull request with policy proposal",
    )

    propose_parser.add_argument(
        "--repo",
        required=True,
        help="GitHub repository (e.g., owner/repo)",
    )

    propose_parser.add_argument(
        "--branch",
        required=True,
        help="Branch name for the PR (e.g., harden/ci-runner-2025-10-18)",
    )

    propose_parser.add_argument(
        "--input",
        required=True,
        help="Path to proposal JSON from analyze command",
    )

    propose_parser.add_argument(
        "--base",
        default="main",
        help="Base branch for PR (default: main)",
    )

    propose_parser.add_argument(
        "--title",
        help="Custom PR title (auto-generated if not provided)",
    )

    propose_parser.add_argument(
        "--draft",
        action="store_true",
        help="Create as draft PR",
    )

    propose_parser.add_argument(
        "--github-token",
        help="GitHub personal access token (or set GITHUB_TOKEN env var)",
    )

    # ===== APPLY COMMAND =====
    apply_parser = subparsers.add_parser(
        "apply",
        help="Execute staged rollout via Step Functions",
    )

    apply_parser.add_argument(
        "--state-machine-arn",
        required=True,
        help="Step Functions state machine ARN",
    )

    apply_parser.add_argument(
        "--proposal",
        required=True,
        help="Path to proposal JSON from analyze command",
    )

    apply_parser.add_argument(
        "--environment",
        choices=["sandbox", "canary", "prod"],
        default="prod",
        help="Target environment (default: prod)",
    )

    apply_parser.add_argument(
        "--canary",
        type=int,
        default=10,
        help="Canary rollout percentage (default: 10)",
    )

    apply_parser.add_argument(
        "--rollback-threshold",
        default="AccessDenied>0.1%",
        help="Rollback threshold expression (default: AccessDenied>0.1%%)",
    )

    apply_parser.add_argument(
        "--require-approval",
        action="store_true",
        help="Require human approval before rollout",
    )

    apply_parser.add_argument(
        "--approval-table",
        help="DynamoDB table name for approvals (required if --require-approval)",
    )

    apply_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing",
    )

    apply_parser.add_argument(
        "--mock-mode",
        action="store_true",
        help="Use deterministic mock execution (no AWS calls)",
    )

    # ===== DIFF COMMAND =====
    diff_parser = subparsers.add_parser(
        "diff",
        help="Compare proposal against current live role state",
    )

    diff_parser.add_argument(
        "--input",
        required=True,
        help="Path to proposal JSON from analyze command",
    )

    diff_parser.add_argument(
        "--role-arn",
        help="Optional role ARN (overrides ARN in proposal)",
    )

    diff_parser.add_argument(
        "--mock-mode",
        action="store_true",
        help="Use deterministic mock data",
    )

    # ===== STATUS COMMAND =====
    status_parser = subparsers.add_parser(
        "status",
        help="Check status of recent policy rollouts for a role",
    )

    status_parser.add_argument(
        "--role-arn",
        required=True,
        help="IAM role ARN to check",
    )

    status_parser.add_argument(
        "--state-machine-arn",
        required=True,
        help="Step Functions state machine ARN",
    )

    status_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of recent rollouts to show (default: 5)",
    )

    status_parser.add_argument(
        "--mock-mode",
        action="store_true",
        help="Use deterministic mock data",
    )

    # ===== ROLLBACK COMMAND =====
    rollback_parser = subparsers.add_parser(
        "rollback",
        help="Emergency rollback to original policy state",
    )

    rollback_parser.add_argument(
        "--proposal",
        required=True,
        help="Path to proposal JSON that should be reverted",
    )

    rollback_parser.add_argument(
        "--state-machine-arn",
        required=True,
        help="Step Functions state machine ARN",
    )

    rollback_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing",
    )

    rollback_parser.add_argument(
        "--mock-mode",
        action="store_true",
        help="Use deterministic mock execution",
    )

    # Parse arguments
    args = parser.parse_args()

    # Route to appropriate command
    try:
        if args.command == "analyze":
            exclude_services = (
                [s.strip() for s in args.exclude_services.split(",")]
                if args.exclude_services
                else None
            )
            suppress_actions = (
                [a.strip() for s in args.suppress_actions.split(",")]
                if args.suppress_actions
                else None
            )

            exit_code = run_analyze(
                role_arn=args.role_arn,
                usage_days=args.usage_days,
                output_path=args.output,
                guardrails=args.guardrails,
                baseline_policy_name=args.baseline_policy_name,
                exclude_services=exclude_services,
                suppress_actions=suppress_actions,
                mock_mode=args.mock_mode,
                output_cloudformation=args.output_cloudformation,
                output_terraform=args.output_terraform,
                timeout_seconds=args.timeout_seconds,
                fast=args.fast,
                bedrock_model_id=args.bedrock_model,
            )

        elif args.command == "propose":
            exit_code = run_propose(
                repo=args.repo,
                branch=args.branch,
                input_path=args.input,
                base=args.base,
                title=args.title,
                draft=args.draft,
                github_token=args.github_token,
            )

        elif args.command == "apply":
            exit_code = run_apply(
                state_machine_arn=args.state_machine_arn,
                proposal_path=args.proposal,
                environment=args.environment,
                canary_percent=args.canary,
                rollback_threshold=args.rollback_threshold,
                require_approval=args.require_approval,
                approval_table=args.approval_table,
                dry_run=args.dry_run,
                mock_mode=args.mock_mode,
            )

        elif args.command == "diff":
            exit_code = run_diff(
                proposal_path=args.input,
                role_arn=args.role_arn,
                mock_mode=args.mock_mode,
            )

        elif args.command == "status":
            exit_code = run_status(
                role_arn=args.role_arn,
                state_machine_arn=args.state_machine_arn,
                limit=args.limit,
                mock_mode=args.mock_mode,
            )

        elif args.command == "rollback":
            exit_code = run_rollback(
                proposal_path=args.proposal,
                state_machine_arn=args.state_machine_arn,
                dry_run=args.dry_run,
                mock_mode=args.mock_mode,
            )

        else:
            parser.print_help()
            exit_code = 1

        # Print exit code explanation
        if exit_code != 0:
            description = EXIT_CODE_DESCRIPTIONS.get(exit_code, "Unknown error")
            print(f"\n💡 Exit code {exit_code}: {description}")

        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)

    except Exception as err:
        logging.exception("Unexpected error")
        print(f"\n❌ Unexpected error: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
