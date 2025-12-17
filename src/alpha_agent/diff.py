from __future__ import annotations

import json
from typing import Iterable, List, Optional, Set

import boto3
from botocore.exceptions import ClientError

from .collector import PolicyGenerationError
from .models import PolicyDiff, PolicyDocument


def _build_iam_client() -> boto3.client:
    return boto3.client("iam")


def _normalize_actions(statements: Iterable[dict]) -> Set[str]:
    actions: Set[str] = set()
    for statement in statements:
        statement_actions = statement.get("Action") or []
        if isinstance(statement_actions, str):
            statement_actions = [statement_actions]
        actions.update(statement_actions)
    return actions


def compute_policy_diff(
    existing: Optional[PolicyDocument], proposed: PolicyDocument
) -> PolicyDiff:
    """
    Produce a simple action-level diff between the existing and proposed policy.
    """
    existing_actions = _normalize_actions(existing.statement) if existing else set()
    proposed_actions = _normalize_actions(proposed.statement)

    added = sorted(proposed_actions - existing_actions)
    removed = sorted(existing_actions - proposed_actions)

    summary_parts: List[str] = []
    if added:
        summary_parts.append(f"+{len(added)} actions")
    if removed:
        summary_parts.append(f"-{len(removed)} actions")
    if not summary_parts:
        summary_parts.append("No action-level changes detected")

    return PolicyDiff(
        existing_policy=existing,
        proposed_policy=proposed,
        added_actions=added,
        removed_actions=removed,
        change_summary=", ".join(summary_parts),
    )


def fetch_inline_policy(
    role_arn: str,
    policy_name: str,
    client: Optional[boto3.client] = None,
) -> Optional[PolicyDocument]:
    """
    Retrieve an inline policy attached to an IAM role.

    Returns None when the policy is not present.
    """
    client = client or _build_iam_client()
    role_name = role_arn.split("/")[-1]
    try:
        response = client.get_role_policy(RoleName=role_name, PolicyName=policy_name)
    except ClientError as err:
        error_code = err.response.get("Error", {}).get("Code")
        if error_code == "NoSuchEntity":
            return None
        raise PolicyGenerationError(f"Unable to read existing policy: {err}") from err

    document = json.loads(response["PolicyDocument"])
    return PolicyDocument.model_validate(document)


def fetch_all_role_policies(
    role_arn: str,
    client: Optional[boto3.client] = None,
) -> PolicyDocument:
    """
    Fetch and aggregate all inline and managed policies for an IAM role.
    """
    client = client or _build_iam_client()
    role_name = role_arn.split("/")[-1]
    all_statements = []

    try:
        # 1. Inline policies
        inline_policies = client.list_role_policies(RoleName=role_name)
        for name in inline_policies.get("PolicyNames", []):
            policy = client.get_role_policy(RoleName=role_name, PolicyName=name)
            doc = json.loads(policy["PolicyDocument"])
            stmts = doc.get("Statement", [])
            if isinstance(stmts, dict): stmts = [stmts]
            all_statements.extend(stmts)

        # 2. Managed policies
        managed_policies = client.list_attached_role_policies(RoleName=role_name)
        for policy_ref in managed_policies.get("AttachedPolicies", []):
            policy_arn = policy_ref["PolicyArn"]
            # Get latest version
            p_desc = client.get_policy(PolicyArn=policy_arn)
            v_id = p_desc["Policy"]["DefaultVersionId"]
            p_ver = client.get_policy_version(PolicyArn=policy_arn, VersionId=v_id)
            doc = json.loads(p_ver["PolicyVersion"]["Document"])
            stmts = doc.get("Statement", [])
            if isinstance(stmts, dict): stmts = [stmts]
            all_statements.extend(stmts)

    except ClientError as err:
        raise PolicyGenerationError(f"Unable to read role policies: {err}") from err

    return PolicyDocument(
        version="2012-10-17",
        statement=all_statements
    )
