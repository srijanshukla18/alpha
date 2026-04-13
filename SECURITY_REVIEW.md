# Security Review - ALPHA Project

**Date**: 2025-12-31
**Reviewer**: Automated Security Audit
**Scope**: Full codebase security audit

---

---

## [CRITICAL] Arbitrary Method Invocation via getattr
- **File**: /Users/srijanshukla/code/projects/active-pending/alpha/lambdas/agentcore_runtime/handler.py:73
- **Type**: Code Injection / Privilege Escalation
- **Description**: Tool name from event is passed directly to `getattr()` without validation.
- **Code snippet**:
```python
tool_name = event["tool_name"]
tool_method = getattr(tools, tool_name, None)
result = tool_method(**tool_input)
```
- **Risk**: Attacker can invoke any method on the AgentCoreTools object including private methods.
- **Recommendation**: Use whitelist of allowed tool names before calling getattr.

---

## [HIGH] Unrestricted IAM Permissions Wildcards
- **File**: /Users/srijanshukla/code/projects/active-pending/alpha/infra/lib/alpha_stack.py:71-87
- **Type**: Excessive IAM Permissions
- **Description**: Lambda execution role has wildcard resource permissions for IAM operations.
- **Risk**: Lambda can modify ANY IAM role in the account, enabling privilege escalation.
- **Recommendation**: Scope down resources to specific role ARNs.

---

## [HIGH] Missing Input Validation on ARN Parameters
- **File**: /Users/srijanshukla/code/projects/active-pending/alpha/src/alpha_agent/diff.py:67
- **Type**: Missing Input Validation
- **Description**: ARN parsing uses naive string split without validation: `role_name = role_arn.split("/")[-1]`
- **Risk**: Malformed ARNs could extract wrong role names.
- **Recommendation**: Validate ARN format with regex.

---

## [HIGH] Missing Input Validation on GitHub Repository Parameter
- **File**: /Users/srijanshukla/code/projects/active-pending/alpha/src/alpha_agent/github.py:43-47
- **Type**: Missing Input Validation / Path Traversal
- **Description**: Repository validation only checks for one slash but doesn't validate format.
- **Risk**: Path traversal sequences (../../) could access unintended GitHub API endpoints.
- **Recommendation**: Validate repo matches `^[a-zA-Z0-9-_.]+/[a-zA-Z0-9-_.]+$`

---

## [HIGH] Unvalidated JSON Deserialization from LLM
- **File**: /Users/srijanshukla/code/projects/active-pending/alpha/src/alpha_agent/reasoning.py:132
- **Type**: Insecure Deserialization
- **Description**: JSON from LLM is parsed without schema validation.
- **Risk**: Prompt injection could make LLM output malicious JSON.
- **Recommendation**: Validate against strict JSON schema before deserializing.

---

## [HIGH] NoSQL Injection Risk in DynamoDB Query
- **File**: /Users/srijanshukla/code/projects/active-pending/alpha/src/alpha_agent/approvals.py:56-64
- **Type**: NoSQL Injection
- **Description**: proposal_id lacks format validation before querying.
- **Recommendation**: Validate proposal_id format, use ExpressionAttributeNames.

---

## [MEDIUM] Information Disclosure in Error Messages
- **File**: Multiple lambda handlers
- **Type**: Information Disclosure
- **Description**: Full exception messages returned to clients.
- **Risk**: Stack traces may leak file paths, AWS account IDs.
- **Recommendation**: Return generic errors to clients, log details server-side.

---

## [MEDIUM] GitHub Token Exposure Risk
- **File**: /Users/srijanshukla/code/projects/active-pending/alpha/lambdas/agentcore_runtime/handler.py:69
- **Type**: Credential Management
- **Description**: GitHub token read from env vars, could be logged.
- **Recommendation**: Use AWS Secrets Manager.

---

## [MEDIUM] Missing Rate Limiting on Slack Webhooks
- **File**: /Users/srijanshukla/code/projects/active-pending/alpha/src/alpha_agent/notifications.py
- **Type**: Denial of Service
- **Description**: No rate limiting on Slack webhook calls.
- **Recommendation**: Implement rate limiting.

---

## [MEDIUM] Missing Timeout on HTTP Requests
- **File**: /Users/srijanshukla/code/projects/active-pending/alpha/src/alpha_agent/notifications.py:43
- **Type**: Denial of Service
- **Description**: Slack webhook POST has no timeout.
- **Recommendation**: Add `timeout=10` parameter.

---

---

## [MEDIUM] Missing HTTPS Certificate Validation
- **File**: /Users/srijanshukla/code/projects/active-pending/alpha/src/alpha_agent/github.py:22-29
- **Type**: Insecure Communication
- **Description**: SSL verification not explicitly set.
- **Recommendation**: Explicitly set `session.verify = True`.

---

## [LOW] Hardcoded Default Values
- **File**: /Users/srijanshukla/code/projects/active-pending/alpha/lambdas/guardrail/handler.py:74-79
- **Type**: Security Misconfiguration
- **Description**: Default guardrail values hardcoded.
- **Recommendation**: Fail explicitly if guardrails not configured.

---

## [LOW] Potential Timing Attack
- **File**: /Users/srijanshukla/code/projects/active-pending/alpha/src/alpha_agent/approvals.py:54-78
- **Type**: Information Disclosure
- **Description**: Approval check returns different response times.
- **Recommendation**: Implement constant-time response behavior.

---

## Summary

**Total Issues Found**: 15
- Critical: 2
- High: 5
- Medium: 6
- Low: 2

**Priority Actions**:
1. Fix command injection (CRITICAL)
2. Add tool name whitelist validation (CRITICAL)
3. Scope down IAM permissions (HIGH)
4. Add input validation for all external inputs (HIGH)
