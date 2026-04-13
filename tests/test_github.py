"""
Tests for alpha_agent.github module.

Tests GitHub client functionality for PR creation.
"""
import pytest
from unittest.mock import MagicMock, patch
import json

from alpha_agent.github import (
    GitHubClient,
    GitHubError,
)


class TestGitHubClient:
    """Tests for GitHubClient class."""

    def test_init_default_api_url(self):
        client = GitHubClient(token="test-token")
        assert client.api_url == "https://api.github.com"

    def test_init_custom_api_url(self):
        client = GitHubClient(token="test-token", api_url="https://github.example.com/api/v3")
        assert client.api_url == "https://github.example.com/api/v3"

    def test_init_strips_trailing_slash(self):
        client = GitHubClient(token="test-token", api_url="https://api.github.com/")
        assert client.api_url == "https://api.github.com"

    def test_headers_set_correctly(self):
        client = GitHubClient(token="test-token")
        headers = client.session.headers

        assert headers["Authorization"] == "Bearer test-token"
        assert "application/vnd.github" in headers["Accept"]
        assert "alpha-agent" in headers["User-Agent"]


class TestCreatePullRequest:
    """Tests for GitHubClient.create_pull_request method."""

    def test_successful_pr_creation(self):
        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {
                "html_url": "https://github.com/owner/repo/pull/123",
                "number": 123
            }
            mock_session.post.return_value = mock_response
            mock_session_class.return_value = mock_session

            client = GitHubClient(token="test-token")
            result = client.create_pull_request(
                repo="owner/repo",
                title="Test PR",
                body="Test body",
                head="feature-branch",
                base="main"
            )

            assert result["number"] == 123
            assert "pull/123" in result["html_url"]

    def test_pr_creation_with_draft(self):
        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"number": 1}
            mock_session.post.return_value = mock_response
            mock_session_class.return_value = mock_session

            client = GitHubClient(token="test-token")
            client.create_pull_request(
                repo="owner/repo",
                title="Test PR",
                body="Test body",
                head="feature-branch",
                draft=True
            )

            call_args = mock_session.post.call_args
            payload = call_args.kwargs["json"]
            assert payload["draft"] is True

    def test_invalid_repo_format(self):
        client = GitHubClient(token="test-token")

        with pytest.raises(GitHubError) as exc_info:
            client.create_pull_request(
                repo="invalid-repo",  # Missing owner/
                title="Test",
                body="Test",
                head="branch"
            )
        assert "owner/name format" in str(exc_info.value)

    def test_invalid_repo_format_too_many_slashes(self):
        client = GitHubClient(token="test-token")

        with pytest.raises(GitHubError):
            client.create_pull_request(
                repo="owner/repo/extra",
                title="Test",
                body="Test",
                head="branch"
            )

    def test_api_error_response(self):
        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 422
            mock_response.text = "Validation Failed"
            mock_session.post.return_value = mock_response
            mock_session_class.return_value = mock_session

            client = GitHubClient(token="test-token")

            with pytest.raises(GitHubError) as exc_info:
                client.create_pull_request(
                    repo="owner/repo",
                    title="Test",
                    body="Test",
                    head="branch"
                )
            assert "422" in str(exc_info.value)

    def test_api_unauthorized(self):
        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Bad credentials"
            mock_session.post.return_value = mock_response
            mock_session_class.return_value = mock_session

            client = GitHubClient(token="invalid-token")

            with pytest.raises(GitHubError) as exc_info:
                client.create_pull_request(
                    repo="owner/repo",
                    title="Test",
                    body="Test",
                    head="branch"
                )
            assert "401" in str(exc_info.value)

    def test_endpoint_format(self):
        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"number": 1}
            mock_session.post.return_value = mock_response
            mock_session_class.return_value = mock_session

            client = GitHubClient(token="test-token")
            client.create_pull_request(
                repo="myorg/myrepo",
                title="Test",
                body="Test",
                head="branch"
            )

            call_args = mock_session.post.call_args
            url = call_args.args[0]
            assert url == "https://api.github.com/repos/myorg/myrepo/pulls"

    def test_payload_format(self):
        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"number": 1}
            mock_session.post.return_value = mock_response
            mock_session_class.return_value = mock_session

            client = GitHubClient(token="test-token")
            client.create_pull_request(
                repo="owner/repo",
                title="My Title",
                body="My Body",
                head="my-branch",
                base="develop"
            )

            call_args = mock_session.post.call_args
            payload = call_args.kwargs["json"]

            assert payload["title"] == "My Title"
            assert payload["body"] == "My Body"
            assert payload["head"] == "my-branch"
            assert payload["base"] == "develop"

    def test_timeout_set(self):
        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"number": 1}
            mock_session.post.return_value = mock_response
            mock_session_class.return_value = mock_session

            client = GitHubClient(token="test-token")
            client.create_pull_request(
                repo="owner/repo",
                title="Test",
                body="Test",
                head="branch"
            )

            call_args = mock_session.post.call_args
            assert call_args.kwargs["timeout"] == 15

    def test_repo_whitespace_stripped(self):
        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"number": 1}
            mock_session.post.return_value = mock_response
            mock_session_class.return_value = mock_session

            client = GitHubClient(token="test-token")
            client.create_pull_request(
                repo="  owner/repo  ",
                title="Test",
                body="Test",
                head="branch"
            )

            call_args = mock_session.post.call_args
            url = call_args.args[0]
            assert "  " not in url
            assert "/owner/repo/" in url


class TestGitHubError:
    """Tests for GitHubError exception."""

    def test_error_message(self):
        error = GitHubError("API request failed")
        assert str(error) == "API request failed"

    def test_inherits_from_runtime_error(self):
        error = GitHubError("Test")
        assert isinstance(error, RuntimeError)
