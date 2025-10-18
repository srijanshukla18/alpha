#!/usr/bin/env python3
"""
Demo CLI for ALPHA - Autonomous Least-Privilege Hardening Agent

This script simulates the ALPHA workflow for hackathon demonstrations.
It shows how ALPHA analyzes IAM roles, proposes least-privilege policies,
and executes staged rollouts.

Usage:
    python demo_cli.py --role-arn arn:aws:iam::123456789012:role/ExampleRole
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Any, Dict

# Demo data - simulated for local testing without AWS credentials
DEMO_CLOUDTRAIL_ACTIVITY = {
    "s3:GetObject": 150,
    "s3:ListBucket": 45,
    "dynamodb:Query": 200,
    "dynamodb:GetItem": 350,
    "logs:PutLogEvents": 500,
}

DEMO_CURRENT_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "*",
            "Resource": "*",
        }
    ],
}

DEMO_PROPOSED_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:ListBucket"],
            "Resource": [
                "arn:aws:s3:::my-app-bucket",
                "arn:aws:s3:::my-app-bucket/*",
            ],
        },
        {
            "Effect": "Allow",
            "Action": ["dynamodb:Query", "dynamodb:GetItem"],
            "Resource": "arn:aws:dynamodb:us-east-1:123456789012:table/my-app-table",
        },
        {
            "Effect": "Allow",
            "Action": "logs:PutLogEvents",
            "Resource": "arn:aws:logs:us-east-1:123456789012:log-group:/aws/lambda/my-app:*",
        },
    ],
}


class Colors:
    """ANSI color codes for terminal output."""

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text:^70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.END}\n")


def print_step(step_num: int, title: str) -> None:
    """Print a step header."""
    print(f"{Colors.BOLD}{Colors.CYAN}Step {step_num}: {title}{Colors.END}")


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"{Colors.BLUE}ℹ {message}{Colors.END}")


def simulate_delay(seconds: float, message: str = "") -> None:
    """Simulate processing time with a message."""
    if message:
        print(f"{Colors.CYAN}{message}...{Colors.END}", end="", flush=True)
    time.sleep(seconds)
    if message:
        print(f" {Colors.GREEN}Done!{Colors.END}")


def demo_step_1_analyze(role_arn: str) -> None:
    """Step 1: Analyze IAM role usage."""
    print_step(1, "Analyzing IAM Role Usage")
    print_info(f"Target Role: {role_arn}")
    simulate_delay(1.5, "Querying IAM Access Analyzer")
    simulate_delay(2, "Analyzing CloudTrail activity (last 30 days)")

    print(f"\n{Colors.BOLD}Activity Summary:{Colors.END}")
    for action, count in DEMO_CLOUDTRAIL_ACTIVITY.items():
        print(f"  • {action:30} {count:5} invocations")

    print_success("CloudTrail analysis complete")


def demo_step_2_current_policy(role_arn: str) -> None:
    """Step 2: Show current policy."""
    print_step(2, "Current Policy Review")
    simulate_delay(1, "Fetching current IAM policy")

    print(f"\n{Colors.BOLD}Current Policy:{Colors.END}")
    print(json.dumps(DEMO_CURRENT_POLICY, indent=2))

    print_warning("Policy grants wildcard (*) permissions on all resources!")
    print_warning("Privilege reduction needed: ~95% of granted permissions unused")


def demo_step_3_bedrock_reasoning() -> None:
    """Step 3: Bedrock reasoning."""
    print_step(3, "Bedrock AI Reasoning")
    simulate_delay(1.5, "Invoking Claude 3.5 Sonnet on Amazon Bedrock")
    simulate_delay(2, "Analyzing usage patterns and generating recommendations")

    print(f"\n{Colors.BOLD}AI Analysis:{Colors.END}")
    print(
        "  The role exhibits access patterns for S3 (read), DynamoDB (query),\n"
        "  and CloudWatch Logs (write). Based on 30 days of telemetry, the\n"
        "  following least-privilege policy is recommended:"
    )

    print(f"\n{Colors.BOLD}Risk Assessment:{Colors.END}")
    print("  • Probability of breakage: 5%")
    print("  • Confidence level: High (1245 datapoints analyzed)")
    print("  • Missing permissions: None detected")

    print_success("Bedrock reasoning complete")


def demo_step_4_proposed_policy() -> None:
    """Step 4: Show proposed policy."""
    print_step(4, "Proposed Least-Privilege Policy")
    simulate_delay(1, "Applying guardrails and generating policy")

    print(f"\n{Colors.BOLD}Proposed Policy:{Colors.END}")
    print(json.dumps(DEMO_PROPOSED_POLICY, indent=2))

    print(f"\n{Colors.BOLD}Policy Diff:{Colors.END}")
    print(f"{Colors.GREEN}  + Added 5 scoped actions{Colors.END}")
    print(f"{Colors.RED}  - Removed wildcard (*) action{Colors.END}")
    print(f"  • Privilege reduction: 95%")
    print(f"  • Resources scoped: 3 ARN patterns")

    print_success("Policy proposal generated")


def demo_step_5_approval() -> None:
    """Step 5: Human approval."""
    print_step(5, "Requesting Human Approval")
    simulate_delay(1, "Sending Slack notification to security team")

    print(f"\n{Colors.BOLD}Approval Request Sent:{Colors.END}")
    print("  Channel: #security-approvals")
    print("  Approvers: security-team@company.com")
    print("  Approval link: https://alpha.internal/approvals/abc123")

    print_info("Waiting for approval...")
    simulate_delay(2, "Polling approval status")
    print_success("✓ Approved by: alice@company.com at " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def demo_step_6_rollout() -> None:
    """Step 6: Staged rollout."""
    print_step(6, "Staged Rollout Execution")

    # Sandbox stage
    print(f"\n{Colors.BOLD}Stage 1: Sandbox{Colors.END}")
    simulate_delay(1.5, "Attaching policy to sandbox role")
    simulate_delay(1, "Monitoring error metrics")
    print_success("Sandbox stage complete - 0 errors detected")

    # Canary stage
    print(f"\n{Colors.BOLD}Stage 2: Canary (10% traffic){Colors.END}")
    simulate_delay(2, "Attaching policy to canary role")
    simulate_delay(1.5, "Monitoring error metrics")
    print_success("Canary stage complete - 0.01% error rate (within threshold)")

    # Production stage
    print(f"\n{Colors.BOLD}Stage 3: Production{Colors.END}")
    simulate_delay(2, "Attaching policy to production role")
    simulate_delay(1, "Monitoring error metrics")
    print_success("Production rollout complete - 0% error rate")

    print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 Policy successfully deployed across all stages!{Colors.END}")


def demo_step_7_metrics() -> None:
    """Step 7: Success metrics."""
    print_step(7, "Success Metrics")

    metrics = {
        "Privilege Reduction": "95%",
        "Actions Before": "All (*)",
        "Actions After": "5 scoped actions",
        "Resources Before": "All (*)",
        "Resources After": "3 scoped ARNs",
        "Rollout Time": "8 minutes",
        "Error Rate": "0%",
        "Approval Time": "2 minutes",
    }

    print(f"\n{Colors.BOLD}Final Results:{Colors.END}")
    for key, value in metrics.items():
        print(f"  • {key:25} {Colors.GREEN}{value}{Colors.END}")

    print_success("Policy hardening complete - role is now least-privileged!")


def run_demo(role_arn: str, skip_approval: bool = False) -> int:
    """Run the full ALPHA demo workflow."""
    print_header("ALPHA - Autonomous Least-Privilege Hardening Agent")
    print_info("Demo Mode: Simulated workflow (no AWS credentials required)")
    print_info(f"Timestamp: {datetime.now().isoformat()}\n")

    try:
        demo_step_1_analyze(role_arn)
        demo_step_2_current_policy(role_arn)
        demo_step_3_bedrock_reasoning()
        demo_step_4_proposed_policy()

        if not skip_approval:
            demo_step_5_approval()

        demo_step_6_rollout()
        demo_step_7_metrics()

        print_header("Demo Complete")
        print_success("ALPHA successfully hardened your IAM role!")
        print_info(
            "In production, this workflow runs automatically via Step Functions"
        )
        print_info("and integrates with AgentCore for advanced agent capabilities")

        return 0

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Demo interrupted by user{Colors.END}")
        return 130
    except Exception as err:
        print(f"\n{Colors.RED}Error during demo: {err}{Colors.END}")
        return 1


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="ALPHA Demo CLI - Simulate IAM policy hardening workflow"
    )
    parser.add_argument(
        "--role-arn",
        default="arn:aws:iam::123456789012:role/my-app-role",
        help="IAM role ARN to analyze",
    )
    parser.add_argument(
        "--skip-approval",
        action="store_true",
        help="Skip the approval step for faster demo",
    )

    args = parser.parse_args()
    sys.exit(run_demo(args.role_arn, args.skip_approval))


if __name__ == "__main__":
    main()
