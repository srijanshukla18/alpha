from __future__ import annotations

import logging
from typing import Dict, Optional

import requests

LOGGER = logging.getLogger(__name__)


class GitHubError(RuntimeError):
    """Raised when interactions with the GitHub API fail."""


class GitHubClient:
    """
    Lightweight GitHub REST API helper for creating pull requests.
    """

    def __init__(self, token: str, api_url: str = "https://api.github.com") -> None:
        self.api_url = api_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "alpha-agent/0.1.0",
            }
        )

    def create_pull_request(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        draft: bool = False,
    ) -> Dict:
        """
        Create a pull request for repo ``owner/name``.
        """
        owner_repo = repo.strip()
        if owner_repo.count("/") != 1:
            raise GitHubError(f"Repository must be in owner/name format, got {repo}")

        endpoint = f"{self.api_url}/repos/{owner_repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
            "draft": draft,
        }
        response = self.session.post(endpoint, json=payload, timeout=15)
        if response.status_code >= 300:
            raise GitHubError(
                f"GitHub PR creation failed ({response.status_code}): {response.text}"
            )
        pr = response.json()
        LOGGER.info("Created PR %s", pr.get("html_url"))
        return pr
