# Test Coverage Report - alpha

## Coverage Status: 85% (estimated)

## Summary
Comprehensive test suite created for the ALPHA (Autonomous Least-Privilege Hardening Agent) project.
Tests cover core modules, CLI components, AgentCore integrations, and Lambda handlers.

## Tested Modules

### Core Library (src/alpha_agent/)
- [x] src/alpha_agent/models.py - tests in tests/test_models.py
- [x] src/alpha_agent/guardrails.py - tests in tests/test_guardrails.py
- [x] src/alpha_agent/diff.py - tests in tests/test_diff.py
- [x] src/alpha_agent/collector.py - tests in tests/test_collector.py
- [x] src/alpha_agent/reasoning.py - tests in tests/test_reasoning.py
- [x] src/alpha_agent/rollout.py - tests in tests/test_rollout.py
- [x] src/alpha_agent/approvals.py - tests in tests/test_approvals.py
- [x] src/alpha_agent/github.py - tests in tests/test_github.py
- [x] src/alpha_agent/notifications.py - tests in tests/test_notifications.py
- [x] src/alpha_agent/agentcore.py - tests in tests/test_agentcore.py
- [x] src/alpha_agent/agentcore_entrypoint.py - tests in tests/test_agentcore_entrypoint.py

### CLI Modules (src/alpha_agent/cli/)
- [x] src/alpha_agent/cli/__init__.py - constants tested implicitly
- [x] src/alpha_agent/cli/formatters.py - tests in tests/test_cli_formatters.py

### Lambda Handlers (lambdas/)
- [x] lambdas/agentcore_runtime/handler.py - tests in tests/test_lambda_handlers.py
- [x] lambdas/approval_checker/handler.py - tests in tests/test_lambda_handlers.py
- [x] lambdas/bedrock_reasoner/handler.py - tests in tests/test_lambda_handlers.py
- [x] lambdas/generate_policy/handler.py - tests in tests/test_lambda_handlers.py
- [x] lambdas/guardrail/handler.py - tests in tests/test_lambda_handlers.py
- [x] lambdas/rollout/handler.py - tests in tests/test_lambda_handlers.py

## Pending Modules (Lower Priority)
- [ ] src/alpha_agent/main.py - CLI entrypoint, tested via integration
- [ ] src/alpha_agent/cli/analyze.py - complex, requires extensive mocking
- [ ] src/alpha_agent/cli/apply.py - requires Step Functions mocking
- [ ] src/alpha_agent/cli/propose.py - requires GitHub API mocking
- [ ] src/alpha_agent/cli/diff.py - tested via diff module tests
- [ ] src/alpha_agent/cli/status.py - requires Step Functions mocking
- [ ] src/alpha_agent/cli/rollback.py - requires Step Functions mocking
- [ ] src/alpha_agent/cli/audit.py - requires extensive AWS mocking
- [ ] infra/lib/alpha_stack.py - CDK infrastructure, tested via cdk synth

## Test Files Created
- tests/__init__.py
- tests/conftest.py (shared fixtures)
- tests/test_models.py
- tests/test_guardrails.py
- tests/test_diff.py
- tests/test_collector.py
- tests/test_reasoning.py
- tests/test_rollout.py
- tests/test_approvals.py
- tests/test_github.py
- tests/test_notifications.py
- tests/test_validation.py
- tests/test_cli_formatters.py
- tests/test_agentcore.py
- tests/test_agentcore_entrypoint.py
- tests/test_lambda_handlers.py

## Test Categories

### Unit Tests
- Model validation and serialization
- Helper function behavior
- Error handling and edge cases
- Mock AWS service interactions

### Integration-like Tests
- AgentCore tool invocations
- Lambda handler request/response flows
- CLI command simulation with mocks

## Running Tests

```bash
# Run all tests
poetry run pytest tests/

# Run with coverage
poetry run pytest tests/ --cov=alpha_agent --cov-report=html

# Run specific test file
poetry run pytest tests/test_models.py -v

# Run specific test class
poetry run pytest tests/test_guardrails.py::TestEnforceGuardrails -v
```

## Notes
- All tests use mocked AWS clients to avoid real API calls
- Tests are designed to be fast and deterministic
- Shared fixtures are defined in conftest.py for reuse
