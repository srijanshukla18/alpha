"""
alpha analyze command

Analyzes IAM role usage and generates least-privilege policy proposal.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Dict

from alpha_agent.cli import EXIT_SUCCESS, EXIT_RISKY, EXIT_GUARDRAIL_VIOLATION, EXIT_ERROR
from alpha_agent.cli.formatters import (
    format_terminal_summary,
    format_json_proposal,
    format_cloudformation_patch,
    format_terraform_patch,
)
from alpha_agent.cli.judge_mode import JudgeModeProvider
from alpha_agent.collector import generate_policy, PolicyGenerationRequest
from alpha_agent.fast_collector import generate_policy_fast
from alpha_agent.diff import compute_policy_diff, fetch_inline_policy
from alpha_agent.guardrails import enforce_guardrails
from alpha_agent.models import PolicyDocument, PolicyProposal, RiskSignal
from alpha_agent.reasoning import BedrockReasoner, BedrockReasoningError

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
    judge_mode: bool = False,
    output_cloudformation: str | None = None,
    output_terraform: str | None = None,
    timeout_seconds: int | None = None,
    fast: bool | None = None,
    bedrock_model_id: str | None = None,
) -> int:
    """
    Run policy analysis for a role.

    Returns exit code based on risk assessment.
    """
    LOGGER.info("Starting policy analysis for %s", role_arn)

    try:
        # Get guardrail configuration
        guardrail_config = GUARDRAIL_PRESETS.get(guardrails, GUARDRAIL_PRESETS["prod"])

        # Add user-specified exclusions
        if exclude_services:
            guardrail_config["disallowed_services"].extend(exclude_services)
        if suppress_actions:
            guardrail_config["blocked_actions"].extend(suppress_actions)

        # Analyze based on mode
        if judge_mode or os.getenv("ALPHA_JUDGE_MODE"):
            print(f"🎭 Judge Mode: Using deterministic mock data\n")
            provider = JudgeModeProvider()

            # Get mock data
            activity = provider.get_cloudtrail_activity(role_arn, usage_days)
            generated_policy = provider.generate_policy_from_activity(activity, role_arn)

            # Get current policy for diff
            existing_policy = provider.get_current_policy(role_arn)

            # Run Bedrock reasoning (mocked)
            context = {
                "role": role_arn,
                "environment": "production",
                "business_impact": "medium",
            }
            proposal = provider.invoke_bedrock_reasoning(generated_policy, context)

        else:
            # Real AWS mode
            fast_mode = bool(int(os.getenv("ALPHA_FAST_MODE", "1"))) if fast is None else fast
            if fast_mode:
                print("⚡ FAST MODE: Using CloudTrail Event History (no Access Analyzer)\n")
            else:
                print(f"☁️  AWS Mode: Calling IAM Access Analyzer and Bedrock\n")

            # Extract account ID and region from role ARN
            # arn:aws:iam::123456789012:role/RoleName
            parts = role_arn.split(":")
            account_id = parts[4]
            region = os.getenv("AWS_REGION", "us-east-1")

            # Build request - use environment variables or defaults
            analyzer_name = os.getenv("ALPHA_ANALYZER_NAME", "alpha-analyzer")
            access_role_name = os.getenv("ALPHA_ACCESS_ROLE_NAME", "AlphaAnalyzerRole")
            trail_name = os.getenv("ALPHA_TRAIL_NAME", "alpha-trail")

            if fast_mode:
                generated_policy = generate_policy_fast(
                    role_arn=role_arn, usage_days=usage_days, region=region
                )
            else:
                request = PolicyGenerationRequest(
                    analyzer_arn=f"arn:aws:access-analyzer:{region}:{account_id}:analyzer/{analyzer_name}",
                    resource_arn=role_arn,
                    cloudtrail_access_role_arn=f"arn:aws:iam::{account_id}:role/{access_role_name}",
                    cloudtrail_trail_arns=[f"arn:aws:cloudtrail:{region}:{account_id}:trail/{trail_name}"],
                    usage_period_days=usage_days,
                )

                # Generate policy from CloudTrail via Access Analyzer
                # Allow override via CLI or env var (ALPHA_ANALYZE_TIMEOUT_SECONDS)
                effective_timeout = (
                    timeout_seconds
                    if timeout_seconds is not None
                    else int(os.getenv("ALPHA_ANALYZE_TIMEOUT_SECONDS", "1800"))
                )
                print(f"⏳ Waiting for Access Analyzer job (timeout {effective_timeout}s)\n")
                generated_policy = generate_policy(request, timeout_seconds=effective_timeout)

            # Get existing policy for diff
            existing_policy = None
            if baseline_policy_name:
                existing_policy = fetch_inline_policy(role_arn, baseline_policy_name)

            # Run Bedrock reasoning
            context = {
                "role": role_arn,
                "environment": "production",
                "business_impact": "medium",
            }
            reasoner = BedrockReasoner(model_id=bedrock_model_id)
            try:
                proposal = reasoner.propose_policy(context, generated_policy)
            except BedrockReasoningError as err:
                LOGGER.warning("Bedrock unavailable, using fallback reasoning: %s", err)
                # Fallback: pass-through proposal with conservative risk signal
                proposal = PolicyProposal(
                    proposed_policy=generated_policy,
                    rationale=(
                        "Fallback reasoning applied due to temporary Bedrock unavailability. "
                        "Using observed CloudTrail actions grouped by service."
                    ),
                    risk_signal=RiskSignal(
                        probability_of_break=0.05,
                        rationale="Observed-only actions; guardrails still enforced.",
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
        elif proposal.risk_signal.probability_of_break > 0.10:
            exit_code = EXIT_RISKY
            print(f"⚠️  Exit code: {exit_code} (high risk detected)")
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
                    "mode": "judge" if judge_mode else "real",
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
