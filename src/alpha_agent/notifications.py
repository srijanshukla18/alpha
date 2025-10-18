from __future__ import annotations

import json
import logging
from typing import Dict, Optional

import requests
from requests import Response

from .models import NotificationPayload

LOGGER = logging.getLogger(__name__)


class NotificationError(RuntimeError):
    """Raised when outgoing notifications fail."""


def send_slack_webhook(
    webhook_url: str,
    payload: NotificationPayload,
    session: Optional[requests.Session] = None,
) -> Response:
    """
    Send a formatted message to Slack via incoming webhook.

    The payload is serialized to a Slack Block Kit layout.
    """
    session = session or requests.Session()
    message = {
        "text": payload.message,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": payload.message}},
        ],
    }

    if payload.metadata:
        fields = []
        for key, value in payload.metadata.items():
            fields.append({"type": "mrkdwn", "text": f"*{key}*\n{value}"})
        message["blocks"].append({"type": "section", "fields": fields})

    response = session.post(webhook_url, data=json.dumps(message))
    if response.status_code >= 400:
        raise NotificationError(
            f"Slack webhook failed with {response.status_code}: {response.text}"
        )
    LOGGER.info("Slack notification sent to %s", payload.channel)
    return response
