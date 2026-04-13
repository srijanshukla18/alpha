"""
Tests for alpha_agent.diff module.

Tests policy diff computation and inline policy fetching.
"""
import pytest
from unittest.mock import MagicMock, patch
import json

from alpha_agent.diff import (
    compute_policy_diff,
    fetch_inline_policy,
    fetch_all_role_policies,
    get_role_action_count,
    _normalize_actions,
    _build_iam_client,
)
from alpha_agent.models import PolicyDocument, PolicyDiff
from alpha_agent.collector import PolicyGenerationError


class TestNormalizeActions:
    """Tests for _normalize_actions helper function."""

    def test_single_action_string(self):
        statements = [{"Action": "s3:GetObject"}]
        actions = _normalize_actions(statements)
        assert actions == {"s3:GetObject"}

    def test_action_list(self):
        statements = [{"Action": ["s3:GetObject", "s3:PutObject"]}]
        actions = _normalize_actions(statements)
        assert actions == {"s3:GetObject", "s3:PutObject"}

    def test_multiple_statements(self):
        statements = [
            {"Action": ["s3:GetObject"]},
            {"Action": ["dynamodb:Query", "dynamodb:Scan"]}
        ]
        actions = _normalize_actions(statements)
        assert len(actions) == 3
        assert "dynamodb:Query" in actions

    def test_missing_action_key(self):
        statements = [{"Effect": "Allow"}]
        actions = _normalize_actions(statements)
        assert actions == set()

    def test_none_action(self):
        statements = [{"Action": None}]
        actions = _normalize_actions(statements)
        assert actions == set()

    def test_empty_statements(self):
        actions = _normalize_actions([])
        assert actions == set()


class TestComputePolicyDiff:
    """Tests for compute_policy_diff function."""

    def test_new_policy_no_existing(self):
        proposed = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}]
        )
        diff = compute_policy_diff(None, proposed)
        assert diff.existing_policy is None
        assert diff.proposed_policy == proposed
        assert "s3:GetObject" in diff.added_actions
        assert diff.removed_actions == []

    def test_no_changes(self):
        policy = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}]
        )
        diff = compute_policy_diff(policy, policy)
        assert diff.added_actions == []
        assert diff.removed_actions == []
        assert "No action-level changes" in diff.change_summary

    def test_added_actions(self):
        existing = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}]
        )
        proposed = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"], "Resource": "*"}]
        )
        diff = compute_policy_diff(existing, proposed)
        assert "s3:PutObject" in diff.added_actions
        assert len(diff.removed_actions) == 0

    def test_removed_actions(self):
        existing = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": ["s3:GetObject", "s3:DeleteObject"], "Resource": "*"}]
        )
        proposed = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}]
        )
        diff = compute_policy_diff(existing, proposed)
        assert "s3:DeleteObject" in diff.removed_actions
        assert len(diff.added_actions) == 0

    def test_mixed_changes(self):
        existing = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": ["s3:GetObject", "s3:DeleteObject"], "Resource": "*"}]
        )
        proposed = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"], "Resource": "*"}]
        )
        diff = compute_policy_diff(existing, proposed)
        assert "s3:PutObject" in diff.added_actions
        assert "s3:DeleteObject" in diff.removed_actions

    def test_change_summary_format(self):
        existing = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}]
        )
        proposed = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"], "Resource": "*"}]
        )
        diff = compute_policy_diff(existing, proposed)
        assert "+2 actions" in diff.change_summary

    def test_wildcard_to_specific(self):
        existing = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": "*", "Resource": "*"}]
        )
        proposed = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}]
        )
        diff = compute_policy_diff(existing, proposed)
        assert "*" in diff.removed_actions
        assert "s3:GetObject" in diff.added_actions

    def test_actions_sorted(self):
        existing = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": ["z:Action", "a:Action"], "Resource": "*"}]
        )
        proposed = PolicyDocument(
            statement=[{"Effect": "Allow", "Action": ["m:Action"], "Resource": "*"}]
        )
        diff = compute_policy_diff(existing, proposed)
        # Verify actions are sorted
        assert diff.added_actions == sorted(diff.added_actions)
        assert diff.removed_actions == sorted(diff.removed_actions)


class TestFetchInlinePolicy:
    """Tests for fetch_inline_policy function."""

    def test_policy_found(self):
        mock_client = MagicMock()
        mock_client.get_role_policy.return_value = {
            "PolicyDocument": json.dumps({
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": "s3:*", "Resource": "*"}]
            })
        }

        policy = fetch_inline_policy(
            "arn:aws:iam::123456789012:role/TestRole",
            "TestPolicy",
            client=mock_client
        )
        assert policy is not None
        assert policy.version == "2012-10-17"
        mock_client.get_role_policy.assert_called_once_with(
            RoleName="TestRole",
            PolicyName="TestPolicy"
        )

    def test_policy_not_found(self):
        mock_client = MagicMock()
        from botocore.exceptions import ClientError
        mock_client.get_role_policy.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity"}},
            "GetRolePolicy"
        )

        policy = fetch_inline_policy(
            "arn:aws:iam::123456789012:role/TestRole",
            "NonExistentPolicy",
            client=mock_client
        )
        assert policy is None

    def test_other_client_error_raises(self):
        mock_client = MagicMock()
        from botocore.exceptions import ClientError
        mock_client.get_role_policy.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}},
            "GetRolePolicy"
        )

        with pytest.raises(PolicyGenerationError):
            fetch_inline_policy(
                "arn:aws:iam::123456789012:role/TestRole",
                "TestPolicy",
                client=mock_client
            )

    def test_role_name_extraction(self):
        mock_client = MagicMock()
        mock_client.get_role_policy.return_value = {
            "PolicyDocument": json.dumps({
                "Version": "2012-10-17",
                "Statement": []
            })
        }

        fetch_inline_policy(
            "arn:aws:iam::123456789012:role/path/to/MyRole",
            "TestPolicy",
            client=mock_client
        )
        mock_client.get_role_policy.assert_called_once_with(
            RoleName="MyRole",
            PolicyName="TestPolicy"
        )


class TestFetchAllRolePolicies:
    """Tests for fetch_all_role_policies function."""

    def test_inline_policies_aggregated(self):
        mock_client = MagicMock()
        mock_client.list_role_policies.return_value = {
            "PolicyNames": ["Policy1", "Policy2"]
        }
        mock_client.get_role_policy.side_effect = [
            {"PolicyDocument": json.dumps({"Statement": [{"Action": "s3:GetObject"}]})},
            {"PolicyDocument": json.dumps({"Statement": [{"Action": "dynamodb:Query"}]})},
        ]
        mock_client.list_attached_role_policies.return_value = {
            "AttachedPolicies": []
        }

        policy = fetch_all_role_policies(
            "arn:aws:iam::123456789012:role/TestRole",
            client=mock_client
        )
        assert len(policy.statement) == 2

    def test_managed_policies_aggregated(self):
        mock_client = MagicMock()
        mock_client.list_role_policies.return_value = {"PolicyNames": []}
        mock_client.list_attached_role_policies.return_value = {
            "AttachedPolicies": [
                {"PolicyArn": "arn:aws:iam::aws:policy/ReadOnlyAccess"}
            ]
        }
        mock_client.get_policy.return_value = {
            "Policy": {"DefaultVersionId": "v1"}
        }
        mock_client.get_policy_version.return_value = {
            "PolicyVersion": {
                "Document": json.dumps({
                    "Statement": [{"Action": "ec2:Describe*"}]
                })
            }
        }

        policy = fetch_all_role_policies(
            "arn:aws:iam::123456789012:role/TestRole",
            client=mock_client
        )
        assert len(policy.statement) == 1

    def test_client_error_raises(self):
        mock_client = MagicMock()
        from botocore.exceptions import ClientError
        mock_client.list_role_policies.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}},
            "ListRolePolicies"
        )

        with pytest.raises(PolicyGenerationError):
            fetch_all_role_policies(
                "arn:aws:iam::123456789012:role/TestRole",
                client=mock_client
            )

    def test_statement_as_dict_normalized(self):
        mock_client = MagicMock()
        mock_client.list_role_policies.return_value = {"PolicyNames": ["Policy1"]}
        mock_client.get_role_policy.return_value = {
            "PolicyDocument": json.dumps({
                "Statement": {"Action": "s3:GetObject"}  # Dict instead of list
            })
        }
        mock_client.list_attached_role_policies.return_value = {"AttachedPolicies": []}

        policy = fetch_all_role_policies(
            "arn:aws:iam::123456789012:role/TestRole",
            client=mock_client
        )
        assert len(policy.statement) == 1


class TestGetRoleActionCount:
    """Tests for get_role_action_count function."""

    def test_count_specific_actions(self):
        mock_client = MagicMock()
        mock_client.list_role_policies.return_value = {"PolicyNames": ["Policy1"]}
        mock_client.get_role_policy.return_value = {
            "PolicyDocument": json.dumps({
                "Statement": [{"Action": ["s3:GetObject", "s3:PutObject"]}]
            })
        }
        mock_client.list_attached_role_policies.return_value = {"AttachedPolicies": []}

        count = get_role_action_count(
            "arn:aws:iam::123456789012:role/TestRole",
            client=mock_client
        )
        assert count == 2

    def test_wildcard_returns_large_number(self):
        mock_client = MagicMock()
        mock_client.list_role_policies.return_value = {"PolicyNames": ["Policy1"]}
        mock_client.get_role_policy.return_value = {
            "PolicyDocument": json.dumps({
                "Statement": [{"Action": "*"}]
            })
        }
        mock_client.list_attached_role_policies.return_value = {"AttachedPolicies": []}

        count = get_role_action_count(
            "arn:aws:iam::123456789012:role/TestRole",
            client=mock_client
        )
        assert count == 10000  # "Infinite" for practical purposes

    def test_no_actions_returns_zero(self):
        mock_client = MagicMock()
        mock_client.list_role_policies.return_value = {"PolicyNames": []}
        mock_client.list_attached_role_policies.return_value = {"AttachedPolicies": []}

        count = get_role_action_count(
            "arn:aws:iam::123456789012:role/TestRole",
            client=mock_client
        )
        assert count == 0
