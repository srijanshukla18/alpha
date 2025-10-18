"""
CDK stack definition for ALPHA agent infrastructure.
"""
from __future__ import annotations

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_lambda_python_alpha as lambda_python,
    aws_logs as logs,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
)
from constructs import Construct


class AlphaStack(Stack):
    """
    CDK stack for ALPHA - Autonomous Least-Privilege Hardening Agent.

    This stack deploys:
    - DynamoDB table for approval tracking
    - Lambda functions for policy generation, reasoning, guardrails, rollout
    - Step Functions state machine for orchestration
    - IAM roles with least-privilege permissions
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDB table for approval tracking
        approval_table = dynamodb.Table(
            self,
            "ApprovalTable",
            table_name="alpha-approvals",
            partition_key=dynamodb.Attribute(
                name="proposal_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # For demo only
        )

        # Common Lambda execution role with necessary permissions
        lambda_role = iam.Role(
            self,
            "AlphaLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )

        # Grant IAM Access Analyzer permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "access-analyzer:StartPolicyGeneration",
                    "access-analyzer:GetGeneratedPolicy",
                ],
                resources=["*"],
            )
        )

        # Grant IAM read/write permissions for policy management
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "iam:GetRole",
                    "iam:GetRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:DeleteRolePolicy",
                    "iam:ListRolePolicies",
                ],
                resources=["*"],  # Scope down in production
            )
        )

        # Grant Bedrock model invocation permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0"
                ],
            )
        )

        # Grant CloudWatch permissions for metrics
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:GetMetricStatistics", "cloudwatch:PutMetricData"],
                resources=["*"],
            )
        )

        # Grant DynamoDB access for approval table
        approval_table.grant_read_write_data(lambda_role)

        # Common environment variables
        common_env = {
            "APPROVAL_TABLE_NAME": approval_table.table_name,
            "LOG_LEVEL": "INFO",
        }

        # Lambda layer with shared dependencies
        shared_layer = lambda_python.PythonLayerVersion(
            self,
            "AlphaSharedLayer",
            entry="../src",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="ALPHA shared agent modules",
        )

        # Lambda function for policy generation
        generate_policy_fn = lambda_.Function(
            self,
            "GeneratePolicyFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../lambdas/generate_policy"),
            layers=[shared_layer],
            role=lambda_role,
            environment=common_env,
            timeout=Duration.minutes(10),
            memory_size=512,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Lambda function for Bedrock reasoning
        bedrock_reasoner_fn = lambda_.Function(
            self,
            "BedrockReasonerFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../lambdas/bedrock_reasoner"),
            layers=[shared_layer],
            role=lambda_role,
            environment=common_env,
            timeout=Duration.minutes(5),
            memory_size=512,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Lambda function for guardrail enforcement
        guardrail_fn = lambda_.Function(
            self,
            "GuardrailFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../lambdas/guardrail"),
            layers=[shared_layer],
            role=lambda_role,
            environment={
                **common_env,
                "GUARDRAIL_BLOCKED_ACTIONS": "iam:PassRole",
                "GUARDRAIL_DISALLOWED_SERVICES": "iam",
            },
            timeout=Duration.minutes(2),
            memory_size=256,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Lambda function for approval checking
        approval_checker_fn = lambda_.Function(
            self,
            "ApprovalCheckerFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../lambdas/approval_checker"),
            layers=[shared_layer],
            role=lambda_role,
            environment=common_env,
            timeout=Duration.seconds(30),
            memory_size=256,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Lambda function for rollout execution
        rollout_fn = lambda_.Function(
            self,
            "RolloutFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../lambdas/rollout"),
            layers=[shared_layer],
            role=lambda_role,
            environment={
                **common_env,
                "CLOUDWATCH_NAMESPACE": "ALPHA/IAM",
            },
            timeout=Duration.minutes(5),
            memory_size=512,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Step Functions state machine role
        sfn_role = iam.Role(
            self,
            "StepFunctionsRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
        )

        # Grant Step Functions permission to invoke Lambdas
        for fn in [
            generate_policy_fn,
            bedrock_reasoner_fn,
            guardrail_fn,
            approval_checker_fn,
            rollout_fn,
        ]:
            fn.grant_invoke(sfn_role)

        # Grant Step Functions permission to access DynamoDB
        approval_table.grant_read_write_data(sfn_role)

        # Define Step Functions tasks
        generate_policy_task = tasks.LambdaInvoke(
            self,
            "GeneratePolicy",
            lambda_function=generate_policy_fn,
            payload=sfn.TaskInput.from_object(
                {
                    "analyzer_arn.$": "$.analyzer_arn",
                    "resource_arn.$": "$.resource_arn",
                    "cloudtrail_access_role_arn.$": "$.cloudtrail_access_role_arn",
                    "cloudtrail_trail_arns.$": "$.cloudtrail_trail_arns",
                    "usage_period_days.$": "$.usage_period_days",
                }
            ),
            result_path="$.generatedPolicy",
            output_path="$",
        )

        reason_task = tasks.LambdaInvoke(
            self,
            "ReasonOverPolicy",
            lambda_function=bedrock_reasoner_fn,
            payload=sfn.TaskInput.from_object(
                {
                    "context.$": "$.context",
                    "policy.$": "$.generatedPolicy.Payload.policy",
                }
            ),
            result_path="$.proposal",
            output_path="$",
        )

        guardrail_task = tasks.LambdaInvoke(
            self,
            "ApplyGuardrails",
            lambda_function=guardrail_fn,
            payload=sfn.TaskInput.from_object(
                {
                    "policy.$": "$.proposal.Payload.proposal",
                }
            ),
            result_path="$.sanitizedProposal",
            output_path="$",
        )

        persist_proposal_task = tasks.DynamoPutItem(
            self,
            "PersistProposal",
            table=approval_table,
            item={
                "proposal_id": tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.context.roleArn")
                ),
                "timestamp": tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$$.State.EnteredTime")
                ),
                "payload": tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.json_to_string(
                        sfn.JsonPath.object_at("$.sanitizedProposal.Payload")
                    )
                ),
            },
            result_path=sfn.JsonPath.DISCARD,
        )

        wait_for_approval = sfn.Wait(
            self,
            "WaitForApproval",
            time=sfn.WaitTime.duration(Duration.minutes(5)),
        )

        check_approval_task = tasks.LambdaInvoke(
            self,
            "CheckApproval",
            lambda_function=approval_checker_fn,
            payload=sfn.TaskInput.from_object(
                {
                    "proposal_id.$": "$.context.roleArn",
                }
            ),
            result_path="$.approvalStatus",
            output_path="$",
        )

        sandbox_rollout_task = tasks.LambdaInvoke(
            self,
            "SandboxRollout",
            lambda_function=rollout_fn,
            payload=sfn.TaskInput.from_object(
                {
                    "stage": "sandbox",
                    "proposal.$": "$.sanitizedProposal.Payload.sanitized_proposal",
                    "role_arn.$": "$.context.roleArn",
                }
            ),
            result_path="$.sandboxOutcome",
            output_path="$",
        )

        canary_rollout_task = tasks.LambdaInvoke(
            self,
            "CanaryRollout",
            lambda_function=rollout_fn,
            payload=sfn.TaskInput.from_object(
                {
                    "stage": "canary",
                    "proposal.$": "$.sanitizedProposal.Payload.sanitized_proposal",
                    "role_arn.$": "$.context.roleArn",
                }
            ),
            result_path="$.canaryOutcome",
            output_path="$",
        )

        target_rollout_task = tasks.LambdaInvoke(
            self,
            "TargetRollout",
            lambda_function=rollout_fn,
            payload=sfn.TaskInput.from_object(
                {
                    "stage": "target",
                    "proposal.$": "$.sanitizedProposal.Payload.sanitized_proposal",
                    "role_arn.$": "$.context.roleArn",
                }
            ),
            result_path="$.targetOutcome",
            output_path="$",
        )

        # Define workflow
        approval_loop = (
            wait_for_approval.next(check_approval_task)
            .next(
                sfn.Choice(self, "ApprovalDecision")
                .when(
                    sfn.Condition.boolean_equals("$.approvalStatus.Payload.approved", True),
                    sandbox_rollout_task,
                )
                .otherwise(wait_for_approval)
            )
        )

        rollout_chain = (
            sandbox_rollout_task.next(
                sfn.Choice(self, "CanaryDecision")
                .when(
                    sfn.Condition.boolean_equals("$.sandboxOutcome.Payload.succeeded", True),
                    canary_rollout_task,
                )
                .otherwise(sfn.Fail(self, "SandboxFailed"))
            )
            .next(
                sfn.Choice(self, "TargetDecision")
                .when(
                    sfn.Condition.boolean_equals("$.canaryOutcome.Payload.succeeded", True),
                    target_rollout_task,
                )
                .otherwise(sfn.Fail(self, "CanaryFailed"))
            )
            .next(sfn.Succeed(self, "Success"))
        )

        definition = (
            generate_policy_task.next(reason_task)
            .next(guardrail_task)
            .next(persist_proposal_task)
            .next(approval_loop)
        )

        # Create state machine
        state_machine = sfn.StateMachine(
            self,
            "AlphaStateMachine",
            state_machine_name="alpha-policy-remediation",
            definition=definition,
            role=sfn_role,
            timeout=Duration.hours(24),
            logs=sfn.LogOptions(
                destination=logs.LogGroup(
                    self,
                    "StateMachineLogGroup",
                    log_group_name="/aws/stepfunctions/alpha",
                    removal_policy=RemovalPolicy.DESTROY,
                ),
                level=sfn.LogLevel.ALL,
            ),
        )
