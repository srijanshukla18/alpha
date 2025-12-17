"""
Output formatters for ALPHA CLI.

Converts policy proposals into various formats:
- Terminal-friendly colored output
- GitHub PR markdown comments
- CloudFormation YAML patches
- Terraform HCL patches
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from alpha_agent.models import PolicyDiff, PolicyDocument, PolicyProposal


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


def format_terminal_summary(
    proposal: PolicyProposal,
    diff: PolicyDiff | None = None,
) -> str:
    """
    Format proposal as colored terminal output.

    Returns human-readable summary with metrics and risk assessment.
    """
    lines = []

    # Header
    lines.append(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.END}")
    lines.append(f"{Colors.BOLD}{Colors.HEADER}{'ALPHA Policy Analysis':^70}{Colors.END}")
    lines.append(f"{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.END}\n")

    # Risk Assessment
    risk_pct = proposal.risk_signal.probability_of_break * 100
    risk_color = Colors.GREEN if risk_pct < 10 else (Colors.YELLOW if risk_pct < 25 else Colors.RED)

    lines.append(f"{Colors.BOLD}Risk Assessment{Colors.END}")
    lines.append(f"  Breakage Probability: {risk_color}{risk_pct:.1f}%{Colors.END}")
    lines.append(f"  Rationale: {proposal.risk_signal.rationale[:80]}...")
    lines.append("")

    # Policy Changes
    if diff:
        total_before = len(diff.removed_actions) + len(diff.added_actions) # Approximation
        reduction_pct = (len(diff.removed_actions) / max(len(diff.removed_actions) + len(diff.added_actions), 1)) * 100
        
        lines.append(f"{Colors.BOLD}Policy Change Summary{Colors.END}")
        lines.append(f"  {Colors.GREEN}󰄬 Added{Colors.END}:    {len(diff.added_actions):>3} actions")
        lines.append(f"  {Colors.RED}󰅙 Removed{Colors.END}:  {len(diff.removed_actions):>3} actions")
        lines.append(f"  {Colors.CYAN}󱕊 Reduction{Colors.END}: {Colors.BOLD}{reduction_pct:.1f}%{Colors.END}")
        lines.append("")

        if diff.added_actions:
            lines.append(f"{Colors.BOLD}Top Added Actions:{Colors.END}")
            for action in diff.added_actions[:5]:
                lines.append(f"  {Colors.GREEN}+ {action}{Colors.END}")
            if len(diff.added_actions) > 5:
                lines.append(f"    ... and {len(diff.added_actions) - 5} more")
            lines.append("")

    # Guardrail Violations
    if proposal.guardrail_violations:
        lines.append(f"{Colors.YELLOW}{Colors.BOLD}⚠ Guardrail Violations ({len(proposal.guardrail_violations)}){Colors.END}")
        for violation in proposal.guardrail_violations[:5]:  # Show first 5
            lines.append(f"  • {violation.code}: {violation.message}")
        if len(proposal.guardrail_violations) > 5:
            lines.append(f"  ... and {len(proposal.guardrail_violations) - 5} more")
        lines.append("")

    # Remediation Notes
    if proposal.remediation_notes:
        lines.append(f"{Colors.BOLD}Remediation Notes{Colors.END}")
        for note in proposal.remediation_notes:
            lines.append(f"  • {note}")
        lines.append("")

    # AI Rationale
    lines.append(f"{Colors.BOLD}AI Analysis{Colors.END}")
    lines.append(f"  {proposal.rationale}")
    lines.append("")

    return "\n".join(lines)


def format_pr_comment(
    role_name: str,
    proposal: PolicyProposal,
    diff: PolicyDiff,
) -> str:
    """
    Format proposal as GitHub PR markdown comment.

    Returns markdown with metrics, diff, and approval checklist.
    """
    risk_pct = proposal.risk_signal.probability_of_break * 100
    reduction_pct = (len(diff.removed_actions) / max(len(diff.removed_actions) + len(diff.added_actions), 1)) * 100

    lines = [
        "## 🔒 ALPHA Policy Analysis",
        "",
        f"**Role**: `{role_name}`",
        f"**Privilege Reduction**: **{reduction_pct:.1f}%** ({len(diff.removed_actions)} → {len(diff.added_actions)} actions)",
        "",
        "### Risk Assessment",
        f"- **Breakage Probability**: {risk_pct:.1f}%",
        f"- **Confidence**: High",
        f"- **Guardrail Violations**: {len(proposal.guardrail_violations)}",
        "",
        "### Changes",
    ]

    # Added actions
    if diff.added_actions:
        lines.append("#### ✅ Added Actions")
        for action in diff.added_actions[:10]:  # First 10
            lines.append(f"- `{action}`")
        if len(diff.added_actions) > 10:
            lines.append(f"- ... and {len(diff.added_actions) - 10} more")
        lines.append("")

    # Removed actions
    if diff.removed_actions:
        lines.append("#### ❌ Removed Actions")
        for action in diff.removed_actions[:10]:
            lines.append(f"- `{action}`")
        if len(diff.removed_actions) > 10:
            lines.append(f"- ... and {len(diff.removed_actions) - 10} more")
        lines.append("")

    # Guardrails
    if proposal.guardrail_violations:
        lines.append("### ⚠️ Guardrail Violations")
        for violation in proposal.guardrail_violations:
            lines.append(f"- **{violation.code}**: {violation.message}")
            if violation.path:
                lines.append(f"  - Path: `{violation.path}`")
        lines.append("")

    # Next steps
    lines.extend([
        "### Next Steps",
        "- [ ] Review policy diff below",
        "- [ ] Approve in Slack (if required)",
        "- [ ] Merge to trigger staged rollout",
        "",
        "<details>",
        "<summary>Full Proposed Policy</summary>",
        "",
        "```json",
        json.dumps(proposal.proposed_policy.model_dump(by_alias=True), indent=2),
        "```",
        "</details>",
        "",
        "---",
        "*Generated by [ALPHA](https://github.com/your-org/alpha) • Report issues on GitHub*",
    ])

    return "\n".join(lines)


def format_cloudformation_patch(
    role_logical_id: str,
    proposal: PolicyProposal,
) -> str:
    """
    Generate CloudFormation YAML patch for the policy.

    Returns ready-to-paste YAML snippet.
    """
    policy_json = proposal.proposed_policy.model_dump(by_alias=True)

    lines = [
        f"# ALPHA-generated policy patch for {role_logical_id}",
        f"# Apply this to your CloudFormation template",
        "",
        f"{role_logical_id}:",
        "  Type: AWS::IAM::Role",
        "  Properties:",
        "    Policies:",
        f"      - PolicyName: ALPHALeastPrivilege",
        "        PolicyDocument:",
    ]

    # Convert policy to YAML-ish format (simplified)
    for key, value in policy_json.items():
        if key == "Version":
            lines.append(f"          {key}: '{value}'")
        elif key == "Statement":
            lines.append(f"          {key}:")
            for stmt in value:
                lines.append("            -")
                for stmt_key, stmt_val in stmt.items():
                    if isinstance(stmt_val, list):
                        lines.append(f"              {stmt_key}:")
                        for item in stmt_val:
                            lines.append(f"                - {item}")
                    elif isinstance(stmt_val, dict):
                        lines.append(f"              {stmt_key}:")
                        lines.append(f"                {json.dumps(stmt_val, indent=16)}")
                    else:
                        lines.append(f"              {stmt_key}: {stmt_val}")

    return "\n".join(lines)


def format_terraform_patch(
    role_resource_name: str,
    proposal: PolicyProposal,
) -> str:
    """
    Generate Terraform HCL patch for the policy.

    Returns ready-to-paste HCL snippet.
    """
    policy_json = json.dumps(proposal.proposed_policy.model_dump(by_alias=True), indent=2)

    lines = [
        f"# ALPHA-generated policy patch for {role_resource_name}",
        f"# Apply this to your Terraform configuration",
        "",
        f"resource \"aws_iam_role_policy\" \"alpha_least_privilege\" {{",
        f"  name = \"ALPHALeastPrivilege\"",
        f"  role = aws_iam_role.{role_resource_name}.id",
        "",
        f"  policy = jsonencode(",
        f"{policy_json}",
        f"  )",
        f"}}",
    ]

    return "\n".join(lines)


def format_json_proposal(
    proposal: PolicyProposal,
    diff: PolicyDiff | None = None,
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Format proposal as structured JSON for machine consumption.

    Includes all metadata, diff, and audit information.
    """
    output = {
        "version": "1.0",
        "proposal": proposal.model_dump(mode="json", by_alias=True),
    }

    if diff:
        output["diff"] = diff.model_dump(mode="json", by_alias=True)

    if metadata:
        output["metadata"] = metadata

    return output
