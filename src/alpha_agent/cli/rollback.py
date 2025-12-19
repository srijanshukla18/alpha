"""
alpha rollback command

Reverts a previously applied policy by applying the original state.
"""
from __future__ import annotations

import json
import logging
from typing import Optional, Dict, Any

import boto3
from alpha_agent.cli import EXIT_SUCCESS, EXIT_ERROR
from alpha_agent.cli.apply import run_apply
from alpha_agent.cli.formatters import Colors

LOGGER = logging.getLogger(__name__)


def run_rollback(
    state_machine_arn: str,
    proposal_path: Optional[str] = None,
    role_arn: Optional[str] = None,
    dry_run: bool = False,
    mock_mode: bool = False,
) -> int:
    """
    Rollback a policy change using the original policy.
    Can use a proposal file or look up history via Step Functions.
    """
    try:
        print(f"\n⏪ {Colors.BOLD}{Colors.RED}Initiating Rollback{Colors.END}")
        
        original_policy = None
        metadata = {}
        target_role = role_arn

        # 1. Try to get from proposal file
        if proposal_path:
            with open(proposal_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            diff = data.get("diff")
            if diff and diff.get("existing_policy"):
                original_policy = diff["existing_policy"]
                metadata = data.get("metadata", {})
                target_role = target_role or metadata.get("role_arn") or metadata.get("roleArn")
                print(f"   Using original policy from file: {proposal_path}")
            else:
                print(f"⚠️  No 'existing_policy' found in {proposal_path}")

        # 2. Try to get from history if still missing
        if not original_policy and target_role:
            if mock_mode:
                print(f"🎭 {Colors.CYAN}Mock Mode: Simulating history lookup...{Colors.END}")
                original_policy = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}]}
            else:
                print(f"🔍 Searching execution history for {target_role}...")
                original_policy = _find_original_policy_from_history(state_machine_arn, target_role)

        if not original_policy:
            print(f"❌ Error: Could not find original policy for rollback.")
            print(f"   Provide a valid --proposal file or a --role-arn with recent ALPHA activity.")
            return EXIT_ERROR

        if not target_role:
            print(f"❌ Error: Target Role ARN unknown.")
            return EXIT_ERROR

        print(f"   Target Role: {target_role}")

        # Construct a "rollback proposal"
        rollback_proposal = {
            "version": "1.0",
            "proposal": {
                "proposed_policy": original_policy,
                "rationale": f"Emergency rollback of ALPHA hardening for {target_role}",
                "risk_signal": {
                    "probability_of_break": 0.0,
                    "rationale": "Restoring previously known good state."
                },
                "guardrail_violations": [],
                "remediation_notes": ["Rollback triggered by SRE"]
            },
            "metadata": {
                **metadata,
                "role_arn": target_role,
                "is_rollback": True,
            }
        }

        # Save to temp file
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            json.dump(rollback_proposal, tmp)
            tmp_path = tmp.name

        try:
            print(f"🚀 {Colors.BOLD}Triggering rollback rollout (100% skip-canary)...{Colors.END}")
            return run_apply(
                state_machine_arn=state_machine_arn,
                proposal_path=tmp_path,
                environment="prod",
                canary_percent=100, 
                rollback_threshold="None",
                require_approval=False, 
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


def _find_original_policy_from_history(state_machine_arn: str, role_arn: str) -> Optional[Dict[str, Any]]:
    """
    Look through Step Functions executions to find the original policy before hardening.
    """
    sfn = boto3.client("stepfunctions")
    paginator = sfn.get_paginator("list_executions")
    
    for page in paginator.paginate(stateMachineArn=state_machine_arn, statusFilter='SUCCEEDED'):
        for execution in page["executions"]:
            desc = sfn.describe_execution(executionArn=execution["executionArn"])
            try:
                input_json = json.loads(desc["input"])
                # Match the role
                exec_role = input_json.get("roleArn") or input_json.get("role_arn")
                if exec_role == role_arn:
                    # Found it! The 'existing_policy' is usually in the 'proposal' or 'diff' field of the input
                    # if we passed the whole bundle, or we can look at the first execution's input.
                    # In our workflow, the 'existing_policy' is stored in the proposal JSON metadata/diff.
                    diff = input_json.get("diff") or {}
                    if diff.get("existing_policy"):
                        return diff["existing_policy"]
            except Exception:
                continue
    return None