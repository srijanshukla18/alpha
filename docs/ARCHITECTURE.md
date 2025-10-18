# ALPHA Architecture

## System Overview

ALPHA (Autonomous Least-Privilege Hardening Agent) is an AWS-native AI agent that automatically discovers over-privileged IAM roles, proposes least-privilege policies using real usage data, and stages safer rollouts with human approval.

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          ALPHA System Architecture                        │
└──────────────────────────────────────────────────────────────────────────┘

                                User Interfaces
                    ┌──────────────┬─────────────┬───────────┐
                    │   Web UI     │  Slack Bot  │ CLI Tool  │
                    └──────┬───────┴──────┬──────┴─────┬─────┘
                           │              │            │
                           └──────────────┼────────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │   API Gateway         │
                              │   (REST API)          │
                              └───────────┬───────────┘
                                          │
                     ┌────────────────────┼────────────────────┐
                     │                    │                    │
                     ▼                    ▼                    ▼
        ┌────────────────────┐ ┌─────────────────┐ ┌──────────────────┐
        │ AgentCore Runtime  │ │ Step Functions  │ │ Direct Lambdas   │
        │ (Agent Executor)   │ │ (Orchestrator)  │ │ (API Endpoints)  │
        └─────────┬──────────┘ └────────┬────────┘ └────────┬─────────┘
                  │                     │                    │
                  │                     │                    │
        ┏━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━┻━━━━━━━━┓
        ┃                    Lambda Functions Layer                    ┃
        ┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
        ┃  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      ┃
        ┃  │   Generate   │  │   Bedrock    │  │  Guardrail   │      ┃
        ┃  │   Policy     │  │  Reasoner    │  │  Enforcer    │      ┃
        ┃  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      ┃
        ┃         │                  │                  │              ┃
        ┃  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐      ┃
        ┃  │  Approval    │  │   Rollout    │  │  AgentCore   │      ┃
        ┃  │  Checker     │  │  Executor    │  │   Handler    │      ┃
        ┃  └──────────────┘  └──────────────┘  └──────────────┘      ┃
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                              │        │        │
                              │        │        │
        ┏━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━┻━━━━━━━━┻━━━━━━━━━━━━━━━━━━━┓
        ┃                   AWS Services Layer                        ┃
        ┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
        ┃  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      ┃
        ┃  │IAM Access    │  │   Amazon     │  │  Amazon IAM  │      ┃
        ┃  │  Analyzer    │  │  Bedrock     │  │              │      ┃
        ┃  │ (Policy Gen) │  │ (Claude 3.5) │  │ (Policy Mgmt)│      ┃
        ┃  └──────────────┘  └──────────────┘  └──────────────┘      ┃
        ┃  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      ┃
        ┃  │  DynamoDB    │  │ CloudWatch   │  │  CloudTrail  │      ┃
        ┃  │ (Approvals)  │  │  (Metrics)   │  │  (Activity)  │      ┃
        ┃  └──────────────┘  └──────────────┘  └──────────────┘      ┃
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

         External Integrations              Storage & Logs
        ┌──────────────┐ ┌──────────────┐  ┌──────────────┐
        │    Slack     │ │    GitHub    │  │   S3 Bucket  │
        │  (Webhook)   │ │     API      │  │  (Artifacts) │
        └──────────────┘ └──────────────┘  └──────────────┘
```

## Component Details

### 1. User Interfaces

#### Web UI (Future Enhancement)
- React-based single-page application
- CloudFront + S3 static hosting
- Real-time policy diff visualization
- Approval workflow interface

#### Slack Integration
- Incoming webhooks for notifications
- Interactive message buttons for approvals
- Slash commands for triggering analysis

#### CLI Tool (demo_cli.py)
- Local testing and demonstration
- Simulates full workflow without AWS credentials
- Colorized terminal output

### 2. Orchestration Layer

#### Step Functions State Machine
Primary workflow orchestrator for production deployments:

```
Start
  ↓
Generate Policy (IAM Access Analyzer)
  ↓
Reason Over Policy (Bedrock Claude)
  ↓
Apply Guardrails
  ↓
Persist Proposal (DynamoDB)
  ↓
Wait for Approval ← ─ ┐
  ↓                   │
Check Approval        │
  ↓                   │
Approved? ─ NO ──────┘
  ↓ YES
Sandbox Rollout
  ↓
Success? ─ NO → Rollback & Fail
  ↓ YES
Canary Rollout
  ↓
Success? ─ NO → Rollback & Fail
  ↓ YES
Production Rollout
  ↓
Success
```

#### AgentCore Runtime
Alternative deployment for agent-driven workflows:
- Fully autonomous operation
- Tool discovery and invocation
- Memory management for context
- Browser automation (optional Nova Act integration)

### 3. Lambda Functions

#### Generate Policy Function
- **Purpose**: Invoke IAM Access Analyzer to generate policies from CloudTrail
- **Input**: Role ARN, CloudTrail configuration, analysis period
- **Output**: Generated policy document
- **Timeout**: 10 minutes (Access Analyzer jobs can be slow)
- **Memory**: 512 MB

#### Bedrock Reasoner Function
- **Purpose**: Use Claude on Bedrock to analyze and refine policies
- **Input**: Generated policy + contextual metadata
- **Output**: Proposal with rationale, risk assessment, remediation notes
- **Timeout**: 5 minutes
- **Memory**: 512 MB

#### Guardrail Function
- **Purpose**: Enforce organizational constraints on policies
- **Input**: Policy proposal
- **Output**: Sanitized policy + violations list
- **Timeout**: 2 minutes
- **Memory**: 256 MB
- **Configuration**: Environment variables for blocked actions, required conditions, disallowed services

#### Approval Checker Function
- **Purpose**: Query DynamoDB for human approval status
- **Input**: Proposal ID
- **Output**: Approval record (approver, timestamp, comments)
- **Timeout**: 30 seconds
- **Memory**: 256 MB

#### Rollout Function
- **Purpose**: Execute staged policy deployment with metrics monitoring
- **Input**: Policy document, stage (sandbox/canary/target), role ARN
- **Output**: Rollout outcome with success/failure + metrics
- **Timeout**: 5 minutes
- **Memory**: 512 MB

#### AgentCore Handler Function
- **Purpose**: Entry point for AgentCore Runtime invocations
- **Input**: Tool name + tool inputs from AgentCore
- **Output**: Tool execution result
- **Timeout**: 15 minutes (for long-running agent tasks)
- **Memory**: 1024 MB

### 4. AWS Services Integration

#### IAM Access Analyzer
- **Purpose**: Generate least-privilege policies from CloudTrail activity
- **APIs Used**:
  - `StartPolicyGeneration` - Initiate analysis job
  - `GetGeneratedPolicy` - Poll for results
- **Input**: Principal ARN, CloudTrail trail ARNs, time window
- **Output**: Policy document with actions/resources observed in use

#### Amazon Bedrock
- **Purpose**: AI-powered policy reasoning and explanation
- **Model**: Claude Sonnet 4.5 (`anthropic.claude-sonnet-4-5-20250929-v1:0`) - Anthropic's most intelligent model
- **Use Cases**:
  - Policy analysis and refinement
  - Risk assessment
  - Human-readable explanations
  - Remediation guidance

#### Amazon IAM
- **APIs Used**:
  - `GetRole` / `GetRolePolicy` - Fetch existing policies
  - `PutRolePolicy` - Attach updated policy
  - `DeleteRolePolicy` - Rollback on failure

#### DynamoDB
- **Table**: `alpha-approvals`
- **Schema**:
  - Partition Key: `proposal_id` (role ARN)
  - Sort Key: `timestamp` (ISO format)
  - Attributes: `approved` (bool), `approver` (string), `comments` (string)
- **Access Patterns**:
  - Write: Record new approval/rejection
  - Read: Query latest approval for proposal ID

#### CloudWatch
- **Metrics**: Custom namespace `ALPHA/IAM`
  - `IAMErrorRate` - Errors after policy changes (per role)
- **Logs**:
  - `/aws/lambda/alpha-*` - Lambda function logs
  - `/aws/stepfunctions/alpha` - State machine execution logs

#### CloudTrail
- **Purpose**: Source of truth for actual IAM usage
- **Integration**: Accessed indirectly via IAM Access Analyzer
- **Configuration**: Multi-region trails recommended for complete coverage

### 5. Data Models

#### PolicyDocument
```python
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": ["arn:aws:s3:::bucket/*"]
    }
  ]
}
```

#### PolicyProposal
```python
{
  "proposed_policy": PolicyDocument,
  "rationale": "Based on 30 days of activity...",
  "risk_signal": {
    "probability_of_break": 0.05,
    "rationale": "High confidence, 1200+ observations"
  },
  "guardrail_violations": [
    {
      "code": "WILDCARD_ACTION",
      "message": "Wildcard actions not allowed",
      "path": "statement[0].Action"
    }
  ],
  "remediation_notes": [
    "Ensure Lambda has ListBucket for pagination"
  ]
}
```

#### PolicyDiff
```python
{
  "existing_policy": PolicyDocument,
  "proposed_policy": PolicyDocument,
  "added_actions": ["s3:GetObject", "s3:ListBucket"],
  "removed_actions": ["*"],
  "change_summary": "+2 actions, -1 actions"
}
```

## Security Considerations

### IAM Permissions
- **Lambda Execution Role**: Least-privilege access to required services
- **AgentCore Identity**: Scoped to specific analysis/remediation tasks
- **Service Roles**: Step Functions has minimal DynamoDB + Lambda permissions

### Data Protection
- **At Rest**: DynamoDB encryption with AWS-managed keys
- **In Transit**: TLS 1.2+ for all API calls
- **Secrets**: Slack webhook URL and GitHub token in Secrets Manager (production)

### Guardrails
- **Mandatory**: Enforced at every proposal stage
- **Configurable**: Environment variables for organization-specific rules
- **Examples**:
  - Block `iam:PassRole` by default
  - Require condition keys (e.g., `aws:RequestedRegion`)
  - Disallow high-risk services

## Deployment Options

### Option 1: Step Functions Orchestration (Production)
- **Pros**: Reliable, auditable, visual workflow
- **Cons**: More complex infrastructure
- **Best For**: Enterprise deployments with compliance requirements

### Option 2: AgentCore Runtime (Agent-Native)
- **Pros**: Fully autonomous, memory-enabled, supports Nova Act browser actions
- **Cons**: Preview service (as of Oct 2025), fewer workflow visualization tools
- **Best For**: Cutting-edge AI agent demos, hackathon submissions

### Option 3: Local/CLI (Development)
- **Pros**: No AWS credentials needed, fast iteration
- **Cons**: Simulated data only
- **Best For**: Demos, testing, local development

## Observability

### Metrics
- Policy generation success rate
- Average proposal approval time
- Rollout stage failure rate
- Privilege reduction percentage

### Logs
- Structured JSON logs from all Lambdas
- CloudWatch Logs Insights queries for troubleshooting
- Step Functions execution history with state transitions

### Tracing (Future)
- X-Ray integration for end-to-end request tracing
- OpenTelemetry spans for AgentCore invocations

## Scalability

### Current Limits
- **Concurrent Analyses**: 10 (Lambda concurrency limit)
- **State Machine Executions**: 1000 concurrent (soft limit)
- **DynamoDB**: On-demand billing (auto-scales)

### Scaling Considerations
- Batch processing for organization-wide role analysis
- SQS queue for asynchronous approval notifications
- EventBridge scheduler for periodic re-analysis

## Future Enhancements

1. **Multi-Account Support**: Cross-account role assumption for centralized governance
2. **Policy Templates**: Pre-approved patterns for common workloads
3. **ML-Based Anomaly Detection**: Flag suspicious privilege escalation attempts
4. **GitHub Integration**: Auto-commit policy changes to IaC repositories
5. **Nova Act Browser Actions**: Demonstrate agent-driven console navigation
6. **Q Developer Integration**: Generate unit tests and refactor Lambda code

## References

- [IAM Access Analyzer Policy Generation](https://docs.aws.amazon.com/IAM/latest/UserGuide/access-analyzer-policy-generation.html)
- [Amazon Bedrock User Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/)
- [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [AWS Step Functions Developer Guide](https://docs.aws.amazon.com/step-functions/latest/dg/)
