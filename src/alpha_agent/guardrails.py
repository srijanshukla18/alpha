from __future__ import annotations

import copy
from typing import Dict, List, Tuple, Optional

from .models import GuardrailViolation, PolicyDocument

WILDCARD_ACTION_VIOLATION = "WILDCARD_ACTION"
MISSING_CONDITION_VIOLATION = "MISSING_CONDITION"
UNSUPPORTED_SERVICE_VIOLATION = "UNSUPPORTED_SERVICE"


def _ensure_list(value):
    if isinstance(value, list):
        return value
    return [value]


def enforce_guardrails(
    policy: PolicyDocument,
    blocked_actions: List[str],
    required_conditions: Dict[str, str],
    disallowed_services: List[str],
    account_id: Optional[str] = None,
    allowed_regions: Optional[List[str]] = None,
) -> Tuple[PolicyDocument, List[GuardrailViolation]]:
    """
    Review and adjust a policy document so it respects organizational guardrails.

    Returns an updated policy document and any violations discovered so they can
    be surfaced to human reviewers.
    """
    updated_policy = copy.deepcopy(policy).model_dump()
    violations: List[GuardrailViolation] = []

    for idx, statement in enumerate(updated_policy["statement"]):
        actions = _ensure_list(statement.get("Action", []))
        resources = _ensure_list(statement.get("Resource", []))

        if any(action == "*" or action.endswith(":*") for action in actions):
            violations.append(
                GuardrailViolation(
                    code=WILDCARD_ACTION_VIOLATION,
                    message="Statements cannot include wildcard actions.",
                    path=f"statement[{idx}].Action",
                )
            )
            statement["Action"] = [
                action for action in actions if action not in {"*", "*:*"}
            ]

        for blocked in blocked_actions:
            if blocked in actions:
                violations.append(
                    GuardrailViolation(
                        code=WILDCARD_ACTION_VIOLATION,
                        message=f"Action {blocked} is blocked by policy.",
                        path=f"statement[{idx}].Action",
                    )
                )
                statement["Action"] = [a for a in actions if a != blocked]

        services = {action.split(":")[0] for action in actions if ":" in action}
        if disallowed_services and services & set(disallowed_services):
            violations.append(
                GuardrailViolation(
                    code=UNSUPPORTED_SERVICE_VIOLATION,
                    message=f"Service(s) {services & set(disallowed_services)} not allowed.",
                    path=f"statement[{idx}]",
                )
            )
            statement["Action"] = [a for a in actions if a.split(":")[0] not in disallowed_services]
            actions = statement["Action"]

        # Special handling for iam:PassRole to ensure scoped resources
        if any(a.lower() == "iam:passrole" for a in actions):
            if account_id:
                scoped = f"arn:aws:iam::{account_id}:role/*"
                if resources == ["*"]:
                    statement["Resource"] = [scoped]
                elif "*" in resources:
                    statement["Resource"] = [r for r in resources if r != "*"] + [scoped]
            else:
                statement["Action"] = [a for a in actions if a.lower() != "iam:passrole"]
            violations.append(
                GuardrailViolation(
                    code=UNSUPPORTED_SERVICE_VIOLATION,
                    message="iam:PassRole must be scoped to specific roles.",
                    path=f"statement[{idx}]",
                )
            )

        conditions = statement.setdefault("Condition", {})
        for key, value in required_conditions.items():
            if key not in conditions:
                violations.append(
                    GuardrailViolation(
                        code=MISSING_CONDITION_VIOLATION,
                        message=f"Condition {key} must be present.",
                        path=f"statement[{idx}].Condition",
                    )
                )
                conditions[key] = value
        if allowed_regions and "aws:RequestedRegion" not in conditions.get("StringEquals", {}):
            conditions.setdefault("StringEquals", {})["aws:RequestedRegion"] = allowed_regions

        # remove empty resource wildcards, add account scoping when possible
        if "*" in resources and len(resources) > 1:
            statement["Resource"] = [r for r in resources if r != "*"]
        elif resources == ["*"] and account_id:
            # add account scoping condition
            conditions.setdefault("StringEquals", {})["aws:ResourceAccount"] = account_id

    sanitized = PolicyDocument(
        version=updated_policy.get("version", "2012-10-17"),
        statement=updated_policy["statement"],
    )
    return sanitized, violations
