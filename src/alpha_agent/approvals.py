from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from .models import ApprovalRecord

LOGGER = logging.getLogger(__name__)


class ApprovalStoreError(RuntimeError):
    """Raised when approval persistence fails."""


class ApprovalStore:
    """
    Wraps a DynamoDB table used to persist human approvals for policy rollouts.

    The table schema is a simple PK/SK model:
      - PK = proposal_id
      - SK = approval timestamp (ISO format)
    """

    def __init__(self, table_name: str, client: Optional[boto3.client] = None) -> None:
        self.table_name = table_name
        self.client = client or boto3.client("dynamodb")

    def record(self, proposal_id: str, approver: str, approved: bool, comments: str = "") -> None:
        record = ApprovalRecord(
            approver=approver,
            approved=approved,
            timestamp=datetime.now(timezone.utc),
            comments=comments or None,
        )
        try:
            self.client.put_item(
                TableName=self.table_name,
                Item={
                    "proposal_id": {"S": proposal_id},
                    "timestamp": {"S": record.timestamp.isoformat()},
                    "approved": {"BOOL": record.approved},
                    "approver": {"S": record.approver},
                    "comments": {"S": record.comments or ""},
                },
            )
        except ClientError as err:
            raise ApprovalStoreError(f"Unable to record approval: {err}") from err
        LOGGER.info("Recorded approval for %s by %s", proposal_id, approver)

    def latest(self, proposal_id: str) -> Optional[ApprovalRecord]:
        try:
            response = self.client.query(
                TableName=self.table_name,
                KeyConditionExpression="proposal_id = :proposal_id",
                ExpressionAttributeValues={
                    ":proposal_id": {"S": proposal_id},
                },
                ScanIndexForward=False,
                Limit=1,
            )
        except ClientError as err:
            raise ApprovalStoreError(f"Unable to fetch approval: {err}") from err

        items = response.get("Items", [])
        if not items:
            return None

        item = items[0]
        return ApprovalRecord(
            approver=item["approver"]["S"],
            approved=item["approved"]["BOOL"],
            timestamp=datetime.fromisoformat(item["timestamp"]["S"]),
            comments=item.get("comments", {}).get("S") or None,
        )
