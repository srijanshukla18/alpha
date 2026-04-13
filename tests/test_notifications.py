"""
Tests for alpha_agent.notifications module.

Tests Slack webhook notification functionality.
"""
import pytest
from unittest.mock import MagicMock, patch
import json

from alpha_agent.notifications import (
    send_slack_webhook,
    NotificationError,
)
from alpha_agent.models import NotificationPayload


class TestSendSlackWebhook:
    """Tests for send_slack_webhook function."""

    def test_successful_notification(self):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        payload = NotificationPayload(
            channel="slack",
            message="Test notification"
        )

        response = send_slack_webhook(
            "https://hooks.slack.com/test",
            payload,
            session=mock_session
        )

        assert response.status_code == 200
        mock_session.post.assert_called_once()

    def test_message_format(self):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        payload = NotificationPayload(
            channel="slack",
            message="Policy update ready"
        )

        send_slack_webhook(
            "https://hooks.slack.com/test",
            payload,
            session=mock_session
        )

        call_args = mock_session.post.call_args
        data = json.loads(call_args.kwargs["data"])

        assert data["text"] == "Policy update ready"
        assert "blocks" in data
        assert data["blocks"][0]["type"] == "section"

    def test_message_with_metadata(self):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        payload = NotificationPayload(
            channel="slack",
            message="Approval required",
            metadata={"Risk": "low", "Role": "TestRole"}
        )

        send_slack_webhook(
            "https://hooks.slack.com/test",
            payload,
            session=mock_session
        )

        call_args = mock_session.post.call_args
        data = json.loads(call_args.kwargs["data"])

        # Should have additional block for fields
        assert len(data["blocks"]) == 2
        fields_block = data["blocks"][1]
        assert fields_block["type"] == "section"
        assert "fields" in fields_block

    def test_error_response_raises(self):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "invalid_payload"
        mock_session.post.return_value = mock_response

        payload = NotificationPayload(
            channel="slack",
            message="Test"
        )

        with pytest.raises(NotificationError) as exc_info:
            send_slack_webhook(
                "https://hooks.slack.com/test",
                payload,
                session=mock_session
            )
        assert "400" in str(exc_info.value)

    def test_server_error_raises(self):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "internal_error"
        mock_session.post.return_value = mock_response

        payload = NotificationPayload(
            channel="slack",
            message="Test"
        )

        with pytest.raises(NotificationError):
            send_slack_webhook(
                "https://hooks.slack.com/test",
                payload,
                session=mock_session
            )

    def test_creates_session_if_not_provided(self):
        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_session.post.return_value = mock_response
            mock_session_class.return_value = mock_session

            payload = NotificationPayload(
                channel="slack",
                message="Test"
            )

            send_slack_webhook(
                "https://hooks.slack.com/test",
                payload
            )

            mock_session_class.assert_called_once()

    def test_block_kit_structure(self):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        payload = NotificationPayload(
            channel="slack",
            message="*Bold* and _italic_ message"
        )

        send_slack_webhook(
            "https://hooks.slack.com/test",
            payload,
            session=mock_session
        )

        call_args = mock_session.post.call_args
        data = json.loads(call_args.kwargs["data"])

        # Verify Block Kit mrkdwn structure
        section = data["blocks"][0]
        assert section["text"]["type"] == "mrkdwn"
        assert "*Bold*" in section["text"]["text"]

    def test_metadata_field_format(self):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        payload = NotificationPayload(
            channel="slack",
            message="Test",
            metadata={"Key1": "Value1", "Key2": "Value2"}
        )

        send_slack_webhook(
            "https://hooks.slack.com/test",
            payload,
            session=mock_session
        )

        call_args = mock_session.post.call_args
        data = json.loads(call_args.kwargs["data"])

        fields_block = data["blocks"][1]
        fields = fields_block["fields"]
        assert len(fields) == 2

        # Each field should be mrkdwn with bold key
        for field in fields:
            assert field["type"] == "mrkdwn"
            assert "*" in field["text"]  # Bold key

    def test_empty_metadata_no_extra_block(self):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        payload = NotificationPayload(
            channel="slack",
            message="Test",
            metadata={}
        )

        send_slack_webhook(
            "https://hooks.slack.com/test",
            payload,
            session=mock_session
        )

        call_args = mock_session.post.call_args
        data = json.loads(call_args.kwargs["data"])

        # Should only have one block (no fields block)
        assert len(data["blocks"]) == 1


class TestNotificationError:
    """Tests for NotificationError exception."""

    def test_error_message(self):
        error = NotificationError("Webhook failed with 400")
        assert "400" in str(error)

    def test_inherits_from_runtime_error(self):
        error = NotificationError("Test")
        assert isinstance(error, RuntimeError)
