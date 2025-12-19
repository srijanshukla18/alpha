"""
alpha audit command

Scans account roles and identifies the most over-privileged ones.
"""
from __future__ import annotations

import logging
import boto3
from typing import List, Dict, Any

from alpha_agent.cli import EXIT_SUCCESS, EXIT_ERROR
from alpha_agent.cli.formatters import Colors
from alpha_agent.diff import get_role_action_count
from alpha_agent.fast_collector import _collect_used_actions

LOGGER = logging.getLogger(__name__)

def run_audit(
    limit: int = 10,
    usage_days: int = 30,
    mock_mode: bool = False,
) -> int:
    """
    Scan account for over-privileged roles.
    """
    print(f"\n🔍 {Colors.BOLD}Auditing account for over-privileged roles...{Colors.END}")
    print(f"   Analysis window: {usage_days} days\n")

    if mock_mode:
        _print_mock_audit()
        return EXIT_SUCCESS

    try:
        iam = boto3.client("iam")
        ct = boto3.client("cloudtrail")
        
        paginator = iam.get_paginator("list_roles")
        roles_to_check = []
        
        print(f"⏳ Scanning roles...")
        for page in paginator.paginate():
            for role in page["Roles"]:
                # Skip service roles usually
                if "/aws-service-role/" in role["Path"]:
                    continue
                roles_to_check.append(role)
                if len(roles_to_check) >= limit * 3: # Scan a reasonable sample
                    break
            if len(roles_to_check) >= limit * 3:
                break

        results = []
        for role in roles_to_check:
            role_arn = role["Arn"]
            try:
                # 1. How many actions does it have?
                granted_count = get_role_action_count(role_arn, iam)
                
                # 2. How many does it actually use?
                # We use a very short timeout for audit speed
                used_actions = _collect_used_actions(ct, role_arn, usage_days, max_seconds=3)
                used_count = len(used_actions)
                
                gap = granted_count - used_count
                
                results.append({
                    "name": role["RoleName"],
                    "arn": role_arn,
                    "granted": granted_count,
                    "used": used_count,
                    "gap": gap
                })
            except Exception:
                continue

        # Sort by gap descending
        results.sort(key=lambda x: x["gap"], reverse=True)
        
        _print_results_table(results[:limit])
        
        return EXIT_SUCCESS

    except Exception as err:
        LOGGER.exception("Audit failed")
        print(f"\n❌ Audit Error: {err}")
        return EXIT_ERROR

def _print_results_table(results: List[Dict[str, Any]]):
    header = f"{'Role Name':<40} {'Granted':<10} {'Used':<10} {'Gap':<10}"
    print(f"{Colors.BOLD}{header}{Colors.END}")
    print("-" * 75)
    
    for r in results:
        granted_str = "Admin (*)" if r["granted"] >= 10000 else str(r["granted"])
        gap_color = Colors.RED if r["gap"] > 100 or r["granted"] >= 10000 else (Colors.YELLOW if r["gap"] > 20 else Colors.GREEN)
        
        print(
            f"{r['name'][:38]:<40} "
            f"{granted_str:<10} "
            f"{r['used']:<10} "
            f"{gap_color}{r['gap']:<10}{Colors.END}"
        )
    
    print(f"\n💡 {Colors.CYAN}Tip: Use 'alpha analyze --role-arn <ARN>' to harden the top roles.{Colors.END}\n")

def _print_mock_audit():
    mock_results = [
        {"name": "AdminRole", "granted": 10000, "used": 45, "gap": 9955},
        {"name": "EC2FullAccess", "granted": 450, "used": 12, "gap": 438},
        {"name": "CI-Runner-Legacy", "granted": 280, "used": 40, "gap": 240},
        {"name": "LambdaExec", "granted": 85, "used": 5, "gap": 80},
        {"name": "ReadOnly", "granted": 1200, "used": 1150, "gap": 50},
    ]
    _print_results_table(mock_results)
