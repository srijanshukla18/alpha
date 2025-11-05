"""
alpha analyze command

Analyzes IAM role usage and generates least-privilege policy proposal.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Dict

from alpha_agent.cli import EXIT_SUCCESS, EXIT_GUARDRAIL_VIOLATION, EXIT_ERROR
from alpha_agent.cli.formatters import (
    format_terminal_summary,
    format_json_proposal,
    format_cloudformation_patch,
    format_terraform_patch,
)
from alpha_agent.fast_collector import generate_policy_fast
from alpha_agent.diff import compute_policy_diff, fetch_inline_policy
from alpha_agent.guardrails import enforce_guardrails
from alpha_agent.models import PolicyDocument, PolicyProposal, RiskSignal

LOGGER = logging.getLogger(__name__)

# Guardrail presets
GUARDRAIL_PRESETS = {
    "none": {
        "blocked_actions": [],
        "required_conditions": {},
        "disallowed_services": [],
    },
    "sandbox": {
        "blocked_actions": ["iam:PassRole"],
        "required_conditions": {},
        "disallowed_services": [],
    },
    "prod": {
        "blocked_actions": ["iam:*", "sts:AssumeRole"],
        "required_conditions": {"StringEquals": {"aws:RequestedRegion": "us-east-1"}},
        "disallowed_services": ["iam", "organizations"],
    },
}


def run_analyze(
    role_arn: str,
    usage_days: int = 30,
    output_path: str | None = None,
    guardrails: str = "prod",
    baseline_policy_name: str | None = None,
    exclude_services: list[str] | None = None,
    suppress_actions: list[str] | None = None,
    output_cloudformation: str | None = None,
    output_terraform: str | None = None,
) -> int:
    """
    Run policy analysis for a role.

    Returns exit code based on risk assessment.
    """
    LOGGER.info("Starting policy analysis for %s", role_arn)

    try:
        # Get guardrail configuration (deep copy to avoid mutating presets)
        import copy
        guardrail_config = copy.deepcopy(GUARDRAIL_PRESETS.get(guardrails, GUARDRAIL_PRESETS["prod"]))

        # Add user-specified exclusions
        if exclude_services:
            guardrail_config["disallowed_services"].extend(exclude_services)
        if suppress_actions:
            guardrail_config["blocked_actions"].extend(suppress_actions)

        # Extract region from environment
        region = os.getenv("AWS_REGION", "us-east-1")

        print("⚡ Analyzing IAM role usage from CloudTrail...\n")

        # Generate policy from CloudTrail Event History
        generated_policy = generate_policy_fast(
            role_arn=role_arn, usage_days=usage_days, region=region
        )

        # Get existing policy for diff
        existing_policy = None
        if baseline_policy_name:
            existing_policy = fetch_inline_policy(role_arn, baseline_policy_name)

        # Create proposal with the generated policy
        proposal = PolicyProposal(
            proposed_policy=generated_policy,
            rationale=f"Policy based on {usage_days} days of CloudTrail activity. Contains only observed actions.",
            risk_signal=RiskSignal(
                probability_of_break=0.05,
                rationale="Policy includes all observed actions from CloudTrail.",
            ),
        )

        # Apply guardrails
        sanitized_policy, violations = enforce_guardrails(
            proposal.proposed_policy,
            blocked_actions=guardrail_config["blocked_actions"],
            required_conditions=guardrail_config["required_conditions"],
            disallowed_services=guardrail_config["disallowed_services"],
        )

        # Update proposal with sanitized policy and violations
        proposal.proposed_policy = sanitized_policy
        proposal.guardrail_violations.extend(violations)

        # Compute diff
        diff = compute_policy_diff(existing_policy, proposal.proposed_policy)

        # Print terminal summary
        print(format_terminal_summary(proposal, diff))

        # Determine exit code
        exit_code = EXIT_SUCCESS
        if len(proposal.guardrail_violations) > 0:
            exit_code = EXIT_GUARDRAIL_VIOLATION
            print(f"⚠️  Exit code: {exit_code} (guardrail violations detected)")
        else:
            print(f"✓ Exit code: {exit_code} (safe to proceed)")

        # Save output if requested
        if output_path:
            output_data = format_json_proposal(
                proposal,
                diff,
                metadata={
                    "role_arn": role_arn,
                    "usage_days": usage_days,
                    "guardrails": guardrails,
                    "exit_code": exit_code,
                },
            )

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2)

            print(f"\n✓ Proposal saved to: {output_path}")

        # Save CloudFormation patch if requested
        if output_cloudformation:
            role_name = role_arn.split("/")[-1]
            cfn_patch = format_cloudformation_patch(role_name, proposal)

            with open(output_cloudformation, "w", encoding="utf-8") as f:
                f.write(cfn_patch)

            print(f"✓ CloudFormation patch saved to: {output_cloudformation}")

        # Save Terraform patch if requested
        if output_terraform:
            role_name = role_arn.split("/")[-1]
            tf_patch = format_terraform_patch(role_name, proposal)

            with open(output_terraform, "w", encoding="utf-8") as f:
                f.write(tf_patch)

            print(f"✓ Terraform patch saved to: {output_terraform}")

        return exit_code

    except Exception as err:
        LOGGER.exception("Analysis failed")
        print(f"\n❌ Error: {err}")
        return EXIT_ERROR
