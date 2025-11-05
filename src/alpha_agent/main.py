"""
ALPHA CLI - IAM Least-Privilege Policy Generator

Analyzes IAM role usage from CloudTrail and generates least-privilege policies.

Commands:
  analyze  - Analyze IAM role usage and generate least-privilege policy
  propose  - Create GitHub PR with policy proposal

Examples:
  # Analyze a role
  alpha analyze --role-arn arn:aws:iam::123:role/MyRole --output proposal.json

  # Create GitHub PR
  alpha propose --repo org/infra --branch harden/role --input proposal.json
"""
from __future__ import annotations

import argparse
import logging
import sys

from alpha_agent.cli import EXIT_CODE_DESCRIPTIONS
from alpha_agent.cli.analyze import run_analyze
from alpha_agent.cli.propose import run_propose

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
        description="ALPHA - IAM Least-Privilege Policy Generator",
        epilog="Analyze CloudTrail usage and generate least-privilege IAM policies",
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
        "--output-cloudformation",
        help="Path to save CloudFormation YAML patch (e.g., cfn-patch.yml)",
    )

    analyze_parser.add_argument(
        "--output-terraform",
        help="Path to save Terraform HCL patch (e.g., tf-patch.tf)",
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
                [a.strip() for a in args.suppress_actions.split(",")]
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
                output_cloudformation=args.output_cloudformation,
                output_terraform=args.output_terraform,
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
