"""
alpha diff command

Compares a proposal against the current live state of an IAM role.
"""
from __future__ import annotations

import json
import logging

from alpha_agent.cli import EXIT_SUCCESS, EXIT_ERROR
from alpha_agent.cli.formatters import Colors, format_terminal_summary
from alpha_agent.diff import compute_policy_diff, fetch_all_role_policies
from alpha_agent.models import PolicyProposal

LOGGER = logging.getLogger(__name__)


def run_diff(
    proposal_path: str,
    role_arn: str | None = None,
    judge_mode: bool = False,
) -> int:
    """
    Compare proposal against live role state.
    """
    try:
        # Load proposal
        with open(proposal_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        proposal = PolicyProposal(**data["proposal"])
        metadata = data.get("metadata", {})
        target_role = role_arn or metadata.get("role_arn") or metadata.get("roleArn")

        if not target_role:
            print(f"❌ Error: Role ARN not found in proposal and not provided via --role-arn")
            return EXIT_ERROR

        print(f"\n🔍 {Colors.BOLD}Diffing proposal against live role:{Colors.END} {target_role}")

        if judge_mode:
            print(f"🎭 {Colors.CYAN}Judge Mode: Simulating diff...{Colors.END}")
            # In judge mode, we just use the diff from the proposal file if it exists,
            # otherwise we mock one.
            from alpha_agent.cli.judge_mode import JudgeModeProvider
            provider = JudgeModeProvider()
            live_policy = provider.get_mock_policy(target_role)
        else:
            # Real mode: fetch from AWS
            live_policy = fetch_all_role_policies(target_role)

        # Compute diff
        diff = compute_policy_diff(live_policy, proposal.proposed_policy)

        # Print summary
        summary = format_terminal_summary(proposal, diff)
        print(summary)

        # Print detailed diff
        if diff.added_actions or diff.removed_actions:
            print(f"{Colors.BOLD}Detailed Action Diff:{Colors.END}")
            for action in diff.added_actions:
                print(f"  {Colors.GREEN}+ {action}{Colors.END}")
            for action in diff.removed_actions:
                print(f"  {Colors.RED}- {action}{Colors.END}")
            print("")
        else:
            print(f"✨ {Colors.GREEN}No action-level differences detected between proposal and live role.{Colors.END}\n")

        return EXIT_SUCCESS

    except Exception as err:
        LOGGER.exception("Diff failed")
        print(f"\n❌ Error: {err}")
        return EXIT_ERROR
