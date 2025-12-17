"""
alpha rollback command

Reverts a previously applied policy by applying the original state.
"""
from __future__ import annotations

import json
import logging

from alpha_agent.cli import EXIT_SUCCESS, EXIT_ERROR
from alpha_agent.cli.apply import run_apply
from alpha_agent.cli.formatters import Colors

LOGGER = logging.getLogger(__name__)


def run_rollback(
    proposal_path: str,
    state_machine_arn: str,
    dry_run: bool = False,
    mock_mode: bool = False,
) -> int:
    """
    Rollback a policy change using the original policy stored in the proposal.
    """
    try:
        print(f"\n⏪ {Colors.BOLD}{Colors.RED}Initiating Rollback{Colors.END}")
        
        # Load proposal
        with open(proposal_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        diff = data.get("diff")
        if not diff or not diff.get("existing_policy"):
            print(f"❌ Error: No 'existing_policy' found in proposal file.")
            print(f"   Rollback requires the original policy to be present in the JSON.")
            return EXIT_ERROR

        metadata = data.get("metadata", {})
        role_arn = metadata.get("role_arn") or metadata.get("roleArn") or "unknown"
        
        print(f"   Target Role: {role_arn}")
        print(f"   Reason: Reverting to pre-ALPHA state recorded in {proposal_path}")

        # Construct a "rollback proposal"
        # We take the existing_policy and make it the proposed_policy
        rollback_proposal = {
            "version": "1.0",
            "proposal": {
                "proposed_policy": diff["existing_policy"],
                "rationale": f"Emergency rollback of ALPHA hardening for {role_arn}",
                "risk_signal": {
                    "probability_of_break": 0.0,
                    "rationale": "Restoring previously known good state."
                },
                "guardrail_violations": [],
                "remediation_notes": ["Rollback triggered by SRE"]
            },
            "metadata": {
                **metadata,
                "is_rollback": True,
                "original_proposal": proposal_path
            }
        }

        # Save rollback proposal to a temp file
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            json.dump(rollback_proposal, tmp)
            tmp_path = tmp.name

        try:
            # Use run_apply to actually execute it
            # For rollback, we usually want to bypass canary and go straight to 100% 
            # or at least have a very aggressive canary.
            print(f"🚀 {Colors.BOLD}Triggering rollback rollout...{Colors.END}")
            
            return run_apply(
                state_machine_arn=state_machine_arn,
                proposal_path=tmp_path,
                environment="prod",
                canary_percent=100, # Rollback fast!
                rollback_threshold="None", # We are already rolling back
                require_approval=False, # SRE bypass for emergency
                dry_run=dry_run,
                mock_mode=mock_mode
            )
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as err:
        LOGGER.exception("Rollback failed")
        print(f"\n❌ Error: {err}")
        return EXIT_ERROR
