from __future__ import annotations

import copy
from typing import Dict, List, Tuple

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

        # remove empty resource wildcards
        if "*" in resources and len(resources) > 1:
            statement["Resource"] = [r for r in resources if r != "*"]

    sanitized = PolicyDocument(
        version=updated_policy.get("version", "2012-10-17"),
        statement=updated_policy["statement"],
    )
    return sanitized, violations
