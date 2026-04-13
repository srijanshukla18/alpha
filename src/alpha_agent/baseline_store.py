from __future__ import annotations

"""
Baseline snapshot persistence for rollback/drift detection.

Uses DynamoDB when BASELINE_TABLE_NAME is configured; otherwise no-ops.
"""
import os
import json
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from .models import PolicyDocument


class BaselineStoreError(RuntimeError):
    """Raised when baseline persistence fails."""


class BaselineStore:
    def __init__(self, table_name: Optional[str] = None, client: Optional[boto3.client] = None) -> None:
        self.table_name = table_name or os.getenv("BASELINE_TABLE_NAME")
        self.client = client or (boto3.client("dynamodb") if self.table_name else None)

    def enabled(self) -> bool:
        return bool(self.table_name and self.client)

    def save(self, role_arn: str, policy: PolicyDocument) -> None:
        if not self.enabled():
            return
        try:
            self.client.put_item(
                TableName=self.table_name,
                Item={
                    "role_arn": {"S": role_arn},
                    "snapshot": {"S": json.dumps(policy.model_dump(by_alias=True))},
                },
            )
        except ClientError as err:
            raise BaselineStoreError(f"Unable to save baseline: {err}") from err

    def load(self, role_arn: str) -> Optional[PolicyDocument]:
        if not self.enabled():
            return None
        try:
            resp = self.client.get_item(
                TableName=self.table_name,
                Key={"role_arn": {"S": role_arn}},
            )
            item = resp.get("Item")
            if not item:
                return None
            snapshot = json.loads(item["snapshot"]["S"])
            return PolicyDocument.model_validate(snapshot)
        except ClientError as err:
            raise BaselineStoreError(f"Unable to load baseline: {err}") from err
