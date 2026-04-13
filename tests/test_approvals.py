"""
Tests for alpha_agent.approvals module.

Tests approval store functionality with DynamoDB.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from alpha_agent.approvals import (
    ApprovalStore,
    ApprovalStoreError,
)
from alpha_agent.models import ApprovalRecord


class TestApprovalStore:
    """Tests for ApprovalStore class."""

    def test_init(self):
        mock_client = MagicMock()
        store = ApprovalStore("test-table", client=mock_client)
        assert store.table_name == "test-table"
        assert store.client == mock_client

    def test_init_creates_client_if_not_provided(self):
        with patch('boto3.client') as mock_boto:
            store = ApprovalStore("test-table")
            mock_boto.assert_called_once_with("dynamodb")


class TestApprovalStoreRecord:
    """Tests for ApprovalStore.record method."""

    def test_record_approval(self):
        mock_client = MagicMock()
        store = ApprovalStore("test-table", client=mock_client)

        store.record(
            proposal_id="test-proposal",
            approver="user@example.com",
            approved=True,
            comments="Approved"
        )

        mock_client.put_item.assert_called_once()
        call_args = mock_client.put_item.call_args
        item = call_args.kwargs["Item"]

        assert item["proposal_id"]["S"] == "test-proposal"
        assert item["approver"]["S"] == "user@example.com"
        assert item["approved"]["BOOL"] is True
        assert item["comments"]["S"] == "Approved"

    def test_record_rejection(self):
        mock_client = MagicMock()
        store = ApprovalStore("test-table", client=mock_client)

        store.record(
            proposal_id="test-proposal",
            approver="admin@example.com",
            approved=False,
            comments="Needs more review"
        )

        call_args = mock_client.put_item.call_args
        item = call_args.kwargs["Item"]
        assert item["approved"]["BOOL"] is False

    def test_record_no_comments(self):
        mock_client = MagicMock()
        store = ApprovalStore("test-table", client=mock_client)

        store.record(
            proposal_id="test-proposal",
            approver="user@example.com",
            approved=True
        )

        call_args = mock_client.put_item.call_args
        item = call_args.kwargs["Item"]
        assert item["comments"]["S"] == ""

    def test_record_timestamp_included(self):
        mock_client = MagicMock()
        store = ApprovalStore("test-table", client=mock_client)

        store.record(
            proposal_id="test-proposal",
            approver="user@example.com",
            approved=True
        )

        call_args = mock_client.put_item.call_args
        item = call_args.kwargs["Item"]
        assert "timestamp" in item
        # Timestamp should be ISO format
        timestamp = item["timestamp"]["S"]
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    def test_record_client_error(self):
        mock_client = MagicMock()
        from botocore.exceptions import ClientError
        mock_client.put_item.side_effect = ClientError(
            {"Error": {"Code": "ValidationException"}},
            "PutItem"
        )
        store = ApprovalStore("test-table", client=mock_client)

        with pytest.raises(ApprovalStoreError):
            store.record(
                proposal_id="test-proposal",
                approver="user@example.com",
                approved=True
            )


class TestApprovalStoreLatest:
    """Tests for ApprovalStore.latest method."""

    def test_latest_found(self):
        mock_client = MagicMock()
        mock_client.query.return_value = {
            "Items": [
                {
                    "proposal_id": {"S": "test-proposal"},
                    "timestamp": {"S": "2025-01-15T10:30:00+00:00"},
                    "approved": {"BOOL": True},
                    "approver": {"S": "user@example.com"},
                    "comments": {"S": "Looks good"}
                }
            ]
        }
        store = ApprovalStore("test-table", client=mock_client)

        record = store.latest("test-proposal")

        assert record is not None
        assert isinstance(record, ApprovalRecord)
        assert record.approver == "user@example.com"
        assert record.approved is True
        assert record.comments == "Looks good"

    def test_latest_not_found(self):
        mock_client = MagicMock()
        mock_client.query.return_value = {"Items": []}
        store = ApprovalStore("test-table", client=mock_client)

        record = store.latest("nonexistent-proposal")

        assert record is None

    def test_latest_no_comments(self):
        mock_client = MagicMock()
        mock_client.query.return_value = {
            "Items": [
                {
                    "proposal_id": {"S": "test-proposal"},
                    "timestamp": {"S": "2025-01-15T10:30:00+00:00"},
                    "approved": {"BOOL": True},
                    "approver": {"S": "user@example.com"}
                    # No comments field
                }
            ]
        }
        store = ApprovalStore("test-table", client=mock_client)

        record = store.latest("test-proposal")

        assert record is not None
        assert record.comments is None

    def test_latest_query_params(self):
        mock_client = MagicMock()
        mock_client.query.return_value = {"Items": []}
        store = ApprovalStore("test-table", client=mock_client)

        store.latest("test-proposal")

        mock_client.query.assert_called_once()
        call_args = mock_client.query.call_args.kwargs

        assert call_args["TableName"] == "test-table"
        assert call_args["KeyConditionExpression"] == "proposal_id = :proposal_id"
        assert call_args["ScanIndexForward"] is False  # Descending order
        assert call_args["Limit"] == 1

    def test_latest_client_error(self):
        mock_client = MagicMock()
        from botocore.exceptions import ClientError
        mock_client.query.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException"}},
            "Query"
        )
        store = ApprovalStore("test-table", client=mock_client)

        with pytest.raises(ApprovalStoreError):
            store.latest("test-proposal")

    def test_latest_timestamp_parsing(self):
        mock_client = MagicMock()
        mock_client.query.return_value = {
            "Items": [
                {
                    "proposal_id": {"S": "test-proposal"},
                    "timestamp": {"S": "2025-01-15T10:30:00+00:00"},
                    "approved": {"BOOL": True},
                    "approver": {"S": "user@example.com"},
                }
            ]
        }
        store = ApprovalStore("test-table", client=mock_client)

        record = store.latest("test-proposal")

        assert record.timestamp == datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)


class TestApprovalStoreError:
    """Tests for ApprovalStoreError exception."""

    def test_error_message(self):
        error = ApprovalStoreError("Failed to record approval")
        assert str(error) == "Failed to record approval"

    def test_inherits_from_runtime_error(self):
        error = ApprovalStoreError("Test")
        assert isinstance(error, RuntimeError)
