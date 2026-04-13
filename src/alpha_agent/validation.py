from __future__ import annotations

"""
Input validation helpers for ALPHA.

These utilities provide lightweight sanity checks for external inputs
that flow into AWS/GitHub APIs to reduce injection/typo risk.
"""

import re

# IAM role ARN validator (account-scoped, no path traversal)
ROLE_ARN_RE = re.compile(
    r"^arn:aws:iam::\d{12}:role(/[A-Za-z0-9+=,.@_-]+)+$"
)

# owner/repo validation for GitHub
REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


def validate_role_arn(role_arn: str) -> None:
    """Raise ValueError if role ARN format is invalid."""
    if not isinstance(role_arn, str) or not ROLE_ARN_RE.match(role_arn):
        raise ValueError(f"Invalid IAM role ARN: {role_arn}")


def validate_repo_slug(repo: str) -> None:
    """Raise ValueError if repo is not owner/repo safe format."""
    if not isinstance(repo, str) or not REPO_RE.match(repo.strip()):
        raise ValueError(f"Invalid repository slug, expected owner/repo: {repo}")
