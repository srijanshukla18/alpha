"""
alpha propose command

Creates a GitHub pull request with the policy proposal.
"""
from __future__ import annotations

import json
import logging
from typing import Dict

from alpha_agent.cli import EXIT_SUCCESS, EXIT_ERROR
from alpha_agent.cli.formatters import format_pr_comment
from alpha_agent.github import GitHubClient, GitHubError
from alpha_agent.models import PolicyDiff, PolicyProposal

LOGGER = logging.getLogger(__name__)


def run_propose(
    repo: str,
    branch: str,
    input_path: str,
    base: str = "main",
    title: str | None = None,
    draft: bool = False,
    github_token: str | None = None,
) -> int:
    """
    Create a GitHub PR with the policy proposal.

    Returns exit code (0 on success, 1 on error).
    """
    LOGGER.info("Creating GitHub PR for %s", repo)

    try:
        # Load proposal from file
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Parse proposal and diff
        proposal = PolicyProposal(**data["proposal"])
        diff_data = data.get("diff")
        diff = PolicyDiff(**diff_data) if diff_data else None

        # Extract role name from metadata
        role_arn = data.get("metadata", {}).get("role_arn", "unknown-role")
        role_name = role_arn.split("/")[-1]

        # Generate PR title if not provided
        if not title:
            reduction_pct = 0
            if diff:
                total = len(diff.added_actions) + len(diff.removed_actions)
                reduction_pct = (len(diff.removed_actions) / max(total, 1)) * 100
            title = f"ALPHA: Harden {role_name} ({reduction_pct:.0f}% privilege reduction)"

        # Generate PR body
        if diff:
            body = format_pr_comment(role_name, proposal, diff)
        else:
            # Fallback if no diff available
            body = f"## ALPHA Policy Proposal\n\n**Role**: `{role_name}`\n\n"
            body += f"**Risk**: {proposal.risk_signal.probability_of_break * 100:.1f}%\n\n"
            body += f"### Proposed Policy\n\n```json\n{json.dumps(proposal.proposed_policy.model_dump(by_alias=True), indent=2)}\n```"

        # Initialize GitHub client
        import os
        token = github_token or os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GitHub token required (set GITHUB_TOKEN or use --github-token)")

        client = GitHubClient(token=token)

        # Create PR
        print(f"\n📝 Creating PR in {repo}...")
        print(f"   Branch: {branch} → {base}")
        print(f"   Title: {title}")

        pr = client.create_pull_request(
            repo=repo,
            title=title,
            body=body,
            head=branch,
            base=base,
            draft=draft,
        )

        pr_url = pr.get("html_url", "")
        pr_number = pr.get("number", "")

        print(f"\n✓ Pull request created successfully!")
        print(f"   URL: {pr_url}")
        print(f"   Number: #{pr_number}")

        return EXIT_SUCCESS

    except GitHubError as err:
        LOGGER.error("GitHub API error: %s", err)
        print(f"\n❌ GitHub API Error: {err}")
        return EXIT_ERROR

    except FileNotFoundError as err:
        LOGGER.error("Input file not found: %s", err)
        print(f"\n❌ File not found: {err}")
        print(f"   Did you run 'alpha analyze' first?")
        return EXIT_ERROR

    except Exception as err:
        LOGGER.exception("PR creation failed")
        print(f"\n❌ Error: {err}")
        return EXIT_ERROR
