"""
ALPHA – Autonomous Least-Privilege Hardening Agent.

This package contains orchestration logic, helper functions, and data models
to collect IAM usage activity, reason about least-privilege policies using
Amazon Bedrock, apply organizational guardrails, and stage rollouts that
require human approval.
"""

from .models import (
    PolicyGenerationRequest,
    PolicyProposal,
    PolicyDiff,
    GuardrailViolation,
    RolloutOutcome,
    PolicyDocument,
    RolloutStage,
    Environment,
)

__all__ = [
    "PolicyGenerationRequest",
    "PolicyProposal",
    "PolicyDiff",
    "GuardrailViolation",
    "RolloutOutcome",
    "PolicyDocument",
    "RolloutStage",
    "Environment",
]
