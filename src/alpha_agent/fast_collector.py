from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

import boto3
from botocore.exceptions import ClientError

from .models import PolicyDocument

LOGGER = logging.getLogger(__name__)


def _build_cloudtrail_client(region: Optional[str] = None) -> boto3.client:
    return boto3.client("cloudtrail", region_name=region)


def _role_name_from_arn(role_arn: str) -> str:
    # arn:aws:iam::123456789012:role/RoleName
    return role_arn.split("/")[-1]


def _event_matches_role(ct_event: Dict, role_arn: str, role_name: str) -> bool:
    """Return True if a CloudTrail event was performed by the role."""
    # Prefer authoritative sessionIssuer ARN match when assuming the role
    ui = ct_event.get("userIdentity", {})
    session_issuer = (
        ui.get("sessionContext", {}).get("sessionIssuer", {}).get("arn")
    )
    if isinstance(session_issuer, str) and session_issuer == role_arn:
        return True

    # Fallback to checking userIdentity.arn which includes assumed-role path
    ui_arn = ui.get("arn")
    if isinstance(ui_arn, str) and role_name in ui_arn:
        return True

    # Top-level Username sometimes contains the assumed role
    username = ct_event.get("userIdentity", {}).get("userName") or ct_event.get(
        "username"
    )
    if isinstance(username, str) and role_name in username:
        return True

    # Resources array occasionally includes the role ARN
    for res in ct_event.get("resources", []) or []:
        arn = res.get("ARN") or res.get("arn")
        if isinstance(arn, str) and arn == role_arn:
            return True

    return False


def _service_prefix(event_source: str) -> Optional[str]:
    # e.g., "s3.amazonaws.com" -> "s3"
    if not event_source or "." not in event_source:
        return None
    return event_source.split(".")[0]


def _collect_used_actions(
    client: boto3.client,
    role_arn: str,
    usage_days: int,
    max_events: int = 2000,
    max_seconds: int = 25,
) -> Set[str]:
    """
    Scan CloudTrail Event History for actions performed by the role.

    Limits by max_events and max_seconds to keep CI/CD fast and predictable.
    """
    start = datetime.now(timezone.utc) - timedelta(days=usage_days)
    end = datetime.now(timezone.utc)

    collected: Set[str] = set()
    pages = 0
    next_token: Optional[str] = None
    t0 = time.time()
    role_name = _role_name_from_arn(role_arn)

    while True:
        if time.time() - t0 > max_seconds:
            LOGGER.info(
                "FAST MODE: Time budget reached (%.1fs). Collected %d actions.",
                time.time() - t0,
                len(collected),
            )
            break

        try:
            kwargs = {"StartTime": start, "EndTime": end, "MaxResults": 50}
            if next_token:
                kwargs["NextToken"] = next_token
            resp = client.lookup_events(**kwargs)
        except ClientError as err:
            raise RuntimeError(f"CloudTrail lookup_events failed: {err}") from err

        pages += 1
        for e in resp.get("Events", []):
            try:
                ct_event = json.loads(e.get("CloudTrailEvent", "{}"))
            except Exception:
                continue

            if not _event_matches_role(ct_event, role_arn, role_name):
                continue

            event_name = e.get("EventName") or ct_event.get("eventName")
            event_source = e.get("EventSource") or ct_event.get("eventSource")
            prefix = _service_prefix(event_source)
            if not prefix or not event_name:
                continue

            # Construct action name (best-effort mapping)
            action = f"{prefix}:{event_name}"
            collected.add(action)

            if len(collected) >= max_events:
                break

        if len(collected) >= max_events:
            LOGGER.info(
                "FAST MODE: Event budget reached (%d actions). Stopping.",
                len(collected),
            )
            break

        next_token = resp.get("NextToken")
        if not next_token:
            break

    return collected


def generate_policy_fast(
    role_arn: str,
    usage_days: int = 30,
    region: Optional[str] = None,
    client: Optional[boto3.client] = None,
) -> PolicyDocument:
    """
    Quick, best-effort policy generator using CloudTrail Event History.

    - No Access Analyzer
    - Finishes in seconds with a time/event budget
    - Approximates IAM actions as servicePrefix:eventName
    - Uses Resource "*" (guardrails refine post-hoc)
    """
    ct = client or _build_cloudtrail_client(region)
    actions = _collect_used_actions(ct, role_arn, usage_days)

    if not actions:
        # If nothing observed, produce a minimal policy allowing zero actions
        # Caller/guardrails/reasoner can decide how to proceed
        LOGGER.warning(
            "FAST MODE: No CloudTrail events found for role in last %d day(s)", usage_days
        )
        return PolicyDocument(
            statement=[{"Effect": "Allow", "Action": [], "Resource": "*"}],
        )

    # Group actions by service for tidy statements
    by_service: Dict[str, List[str]] = defaultdict(list)
    for a in sorted(actions):
        svc = a.split(":", 1)[0]
        by_service[svc].append(a)

    statements: List[Dict] = []
    for svc, svc_actions in sorted(by_service.items()):
        statements.append({
            "Sid": f"Allow{svc.capitalize()}UsedActions",
            "Effect": "Allow",
            "Action": sorted(set(svc_actions)),
            "Resource": "*",
        })

    return PolicyDocument(statement=statements)
