"""
alpha status command

Checks the status of recent policy rollouts for a given role.
"""
from __future__ import annotations

import logging
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from alpha_agent.cli import EXIT_SUCCESS, EXIT_ERROR
from alpha_agent.cli.formatters import Colors

LOGGER = logging.getLogger(__name__)


def run_status(
    role_arn: str,
    state_machine_arn: str,
    limit: int = 5,
    judge_mode: bool = False,
) -> int:
    """
    Check status of recent rollouts for a role.
    """
    print(f"\n🔍 {Colors.BOLD}Checking rollout status for role:{Colors.END} {role_arn}")

    if judge_mode:
        print(f"🎭 {Colors.CYAN}Judge Mode: Returning mock rollout status...{Colors.END}")
        _print_status_entry(
            execution_id="exec-12345",
            status="SUCCEEDED",
            start_date=datetime.now(),
            environment="prod",
            canary="10%",
        )
        return EXIT_SUCCESS

    try:
        sfn = boto3.client("stepfunctions")

        # List executions for the state machine
        # Note: Step Functions doesn't support server-side filtering by input content easily
        # so we list and filter client-side for the recent ones.
        paginator = sfn.get_paginator("list_executions")
        response_iterator = paginator.paginate(
            stateMachineArn=state_machine_arn,
            maxResults=100,  # Look at last 100 executions
        )

        found = 0
        print(f"{'Execution ID':<40} {'Status':<15} {'Environment':<12} {'Started':<20}")
        print("-" * 90)

        for page in response_iterator:
            for execution in page["executions"]:
                # We need to describe the execution to see the input (to match role_arn)
                # This might be slow if there are many executions, but okay for a status command.
                desc = sfn.describe_execution(executionArn=execution["executionArn"])
                input_data = desc.get("input", "{}")
                try:
                    input_json = desc.get("input_json") or {} # handle possible pre-parsed
                    if not input_json:
                        import json
                        input_json = json.loads(input_data)
                    
                    target_role = input_json.get("roleArn") or input_json.get("role_arn")
                    
                    if target_role == role_arn:
                        status = execution["status"]
                        status_color = _get_status_color(status)
                        
                        env = input_json.get("environment", "unknown")
                        canary = input_json.get("canaryPercent", "N/A")
                        if canary != "N/A":
                            canary = f"{canary}%"
                            
                        print(
                            f"{execution['name']:<40} "
                            f"{status_color}{status:<15}{Colors.END} "
                            f"{env:<12} "
                            f"{execution['startDate'].strftime('%Y-%m-%d %H:%M'):<20}"
                        )
                        
                        found += 1
                        if found >= limit:
                            break
                except Exception:
                    continue
            
            if found >= limit:
                break

        if found == 0:
            print(f"\nℹ️  No recent rollouts found for this role in {state_machine_arn}")
        
        return EXIT_SUCCESS

    except ClientError as err:
        LOGGER.error("AWS API error: %s", err)
        print(f"\n❌ AWS API Error: {err}")
        return EXIT_ERROR
    except Exception as err:
        LOGGER.exception("Status check failed")
        print(f"\n❌ Error: {err}")
        return EXIT_ERROR


def _get_status_color(status: str) -> str:
    if status == "SUCCEEDED":
        return Colors.GREEN
    if status == "FAILED":
        return Colors.RED
    if status == "RUNNING":
        return Colors.CYAN
    if status == "ABORTED" or status == "TIMED_OUT":
        return Colors.YELLOW
    return ""


def _print_status_entry(execution_id, status, start_date, environment, canary):
    status_color = _get_status_color(status)
    print(f"{'Execution ID':<40} {'Status':<15} {'Environment':<12} {'Started':<20}")
    print("-" * 90)
    print(
        f"{execution_id:<40} "
        f"{status_color}{status:<15}{Colors.END} "
        f"{environment:<12} "
        f"{start_date.strftime('%Y-%m-%d %H:%M'):<20}"
    )
    print(f"\n📊 {Colors.BOLD}Rollout Details:{Colors.END}")
    print(f"   Canary: {canary}")
    print(f"   Link: https://console.aws.amazon.com/states/home#/executions/details/{execution_id}")
