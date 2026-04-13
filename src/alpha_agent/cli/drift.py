"""
alpha drift command

Compares live role policies against stored baseline to detect drift.
"""
from __future__ import annotations

import logging

from alpha_agent.cli import EXIT_SUCCESS, EXIT_ERROR
from alpha_agent.cli.formatters import Colors, format_terminal_summary
from alpha_agent.baseline_store import BaselineStore
from alpha_agent.diff import compute_policy_diff, fetch_all_role_policies
from alpha_agent.validation import validate_role_arn

LOGGER = logging.getLogger(__name__)


def run_drift(
    role_arn: str,
) -> int:
    """
    Detect drift by comparing live policy to stored baseline.
    """
    try:
        validate_role_arn(role_arn)
        store = BaselineStore()
        if not store.enabled():
            print("❌ Baseline store not configured (set BASELINE_TABLE_NAME).")
            return EXIT_ERROR

        baseline = store.load(role_arn)
        if not baseline:
            print(f"❌ No baseline snapshot found for {role_arn}")
            return EXIT_ERROR

        live_policy = fetch_all_role_policies(role_arn)
        diff = compute_policy_diff(baseline, live_policy)

        # Render simple summary
        print(f"\n🔍 {Colors.BOLD}Drift Detection for{Colors.END} {role_arn}")
        if diff.added_actions or diff.removed_actions:
            print(f"{Colors.YELLOW}⚠ Drift detected.{Colors.END}")
            print(f"  Added actions: {len(diff.added_actions)}")
            print(f"  Removed actions: {len(diff.removed_actions)}")
            if diff.added_actions:
                print("  Examples (added):")
                for a in diff.added_actions[:5]:
                    print(f"    + {a}")
            if diff.removed_actions:
                print("  Examples (removed):")
                for a in diff.removed_actions[:5]:
                    print(f"    - {a}")
        else:
            print(f"{Colors.GREEN}✓ No drift detected.{Colors.END}")

        return EXIT_SUCCESS
    except Exception as err:
        LOGGER.exception("Drift detection failed")
        print(f"\n❌ Error: {err}")
        return EXIT_ERROR
