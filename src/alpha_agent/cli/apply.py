"""
alpha apply command

Triggers Step Functions state machine for staged policy rollout.
"""
from __future__ import annotations

import json
import logging
from typing import Dict

import boto3
from botocore.exceptions import ClientError

from alpha_agent.cli import EXIT_SUCCESS, EXIT_ERROR
from alpha_agent.cli.mock_mode import MockModeProvider
from alpha_agent.approvals import ApprovalStore
from alpha_agent.models import PolicyProposal

LOGGER = logging.getLogger(__name__)


def run_apply(
    state_machine_arn: str,
    proposal_path: str,
    environment: str = "prod",
    canary_percent: int = 10,
    rollback_threshold: str = "AccessDenied>0.1%",
    require_approval: bool = False,
    approval_table: str | None = None,
    dry_run: bool = False,
    mock_mode: bool = False,
) -> int:
    """
    Apply policy via Step Functions staged rollout.

    Returns exit code (0 on success, 1 on error).
    """
    LOGGER.info("Applying policy to %s environment", environment)

    try:
        # Load proposal from file
        with open(proposal_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        proposal = PolicyProposal(**data["proposal"])
        metadata = data.get("metadata", {})
        role_arn = metadata.get("role_arn") or metadata.get("roleArn") or "unknown-role"

        # Check approval if required
        if require_approval:
            print(f"\n🔍 Checking approval status...")

            if mock_mode:
                # Mock mode: always approved
                provider = MockModeProvider()
                approved = provider.check_approval_status(role_arn)
            else:
                # Real mode: query DynamoDB
                if not approval_table:
                    print(f"❌ Error: --approval-table required when --require-approval is set")
                    return EXIT_ERROR

                store = ApprovalStore(approval_table)
                latest = store.latest(role_arn)
                approved = latest and latest.approved if latest else False

            if not approved:
                print(f"⚠️  No approval found for {role_arn}")
                print(f"   Approval required before applying policy")
                print(f"   Use Slack approval workflow or update DynamoDB directly")
                return EXIT_ERROR

            print(f"✓ Approval confirmed")

        # Build Step Functions input
        input_payload = {
            "roleArn": role_arn,
            "environment": environment,
            "canaryPercent": canary_percent,
            "rollbackThreshold": rollback_threshold,
            "proposal": proposal.model_dump(mode="json", by_alias=True),
            "metadata": metadata,
        }

        # Dry run mode
        if dry_run:
            print(f"\n🧪 DRY RUN MODE")
            print(f"   Would start Step Functions execution:")
            print(f"   State Machine: {state_machine_arn}")
            print(f"   Environment: {environment}")
            print(f"   Canary: {canary_percent}%")
            print(f"   Rollback Threshold: {rollback_threshold}")
            print(f"\n   Input payload:")
            print(json.dumps(input_payload, indent=2))
            return EXIT_SUCCESS

        # Start execution
        if mock_mode:
            # Mock mode: mock execution
            print(f"\n🎭 Mock Mode: Simulating Step Functions execution...")
            provider = MockModeProvider()
            execution_arn = provider.start_step_functions_execution(state_machine_arn, input_payload)
        else:
            # Real mode: start actual execution
            print(f"\n🚀 Starting Step Functions execution...")
            client = boto3.client("stepfunctions")

            response = client.start_execution(
                stateMachineArn=state_machine_arn,
                input=json.dumps(input_payload),
            )

            execution_arn = response["executionArn"]

        print(f"✓ Rollout started successfully!")
        print(f"   Execution ARN: {execution_arn}")
        print(f"   Environment: {environment}")
        print(f"   Canary: {canary_percent}%")
        print(f"\n   Monitor progress:")
        try:
            region = state_machine_arn.split(":")[3]
        except IndexError:
            region = "us-east-1"
        print(
            "   "
            f"https://console.aws.amazon.com/states/home?region={region}#/executions/details/{execution_arn}"
        )

        return EXIT_SUCCESS

    except ClientError as err:
        LOGGER.error("AWS API error: %s", err)
        print(f"\n❌ AWS API Error: {err}")
        return EXIT_ERROR

    except FileNotFoundError as err:
        LOGGER.error("Input file not found: %s", err)
        print(f"\n❌ File not found: {err}")
        print(f"   Did you run 'alpha analyze' first?")
        return EXIT_ERROR

    except Exception as err:
        LOGGER.exception("Apply failed")
        print(f"\n❌ Error: {err}")
        return EXIT_ERROR
