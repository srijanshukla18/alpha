"""
ALPHA CLI Package

Provides command-line interface for IAM least-privilege hardening.
Supports three modes: analyze, propose, apply.
"""
from __future__ import annotations

__version__ = "1.0.0"

# Exit codes for CI/CD integration
EXIT_SUCCESS = 0           # Analysis complete, safe to proceed
EXIT_ERROR = 1            # Tool error (bad args, API failure, etc.)
EXIT_GUARDRAIL_VIOLATION = 3  # Guardrail constraints violated

EXIT_CODE_DESCRIPTIONS = {
    EXIT_SUCCESS: "Success - safe to proceed",
    EXIT_ERROR: "Error - tool failure",
    EXIT_GUARDRAIL_VIOLATION: "Guardrail violation - policy blocked",
}
