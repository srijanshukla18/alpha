#!/usr/bin/env python3
"""
ALPHA - Detailed Architecture Diagram
Generates: alpha_architecture_detailed.png
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.integration import StepFunctions
from diagrams.aws.ml import Bedrock
from diagrams.aws.security import IAMAccessAnalyzer, IdentityAndAccessManagementIam
from diagrams.aws.management import Cloudtrail
from diagrams.aws.management import Cloudwatch
from diagrams.aws.database import Dynamodb
from diagrams.aws.storage import S3
from diagrams.aws.devtools import CLI
from diagrams.onprem.vcs import Github
from diagrams.onprem.client import User

graph_attr = {
    "fontsize": "14",
    "bgcolor": "white",
    "pad": "0.5",
}

with Diagram("ALPHA - Detailed Architecture",
             show=False,
             direction="LR",
             graph_attr=graph_attr,
             filename="alpha_architecture_detailed"):

    user = User("DevOps\nEngineer")

    with Cluster("CLI Interface"):
        cli = CLI("alpha CLI\n(Poetry)")
        cli_analyze = Lambda("analyze")
        cli_propose = Lambda("propose")
        cli_apply = Lambda("apply")

    with Cluster("AgentCore Runtime"):
        agentcore = Lambda("agentcore_entrypoint.py")
        action_analyze = Lambda("analyze_fast_policy")
        action_guardrails = Lambda("enforce_guardrails")

    with Cluster("Data Collection Layer"):
        with Cluster("Fast Mode (Default)"):
            cloudtrail = Cloudtrail("CloudTrail\nEvent History\nLookupEvents API")
            fast_collector = Lambda("fast_collector.py")

        with Cluster("Analyzer Mode (Optional)"):
            analyzer = IAMAccessAnalyzer("IAM Access\nAnalyzer")
            analyzer_collector = Lambda("collector.py\nStartPolicyGeneration")

    with Cluster("AI & Reasoning"):
        bedrock_cluster = Bedrock("Amazon Bedrock")
        claude = Lambda("Claude\nSonnet 4.5")
        nova = Lambda("Nova\nPro")
        reasoning = Lambda("reasoning.py\nProvider-aware")

    with Cluster("Policy Processing"):
        guardrails = IdentityAndAccessManagementIam("guardrails.py\nPresets:\nnone/sandbox/prod")
        diff_engine = Lambda("diff.py\nBefore/After")
        formatters = Lambda("formatters.py\nJSON/CFN/TF")

    with Cluster("Outputs"):
        s3_json = S3("proposal.json")
        s3_cfn = S3("cfn-patch.yml")
        s3_tf = S3("tf-patch.tf")
        github = Github("GitHub PR\nw/ metrics")

    with Cluster("Staged Rollout (Optional)"):
        stepfn = StepFunctions("Step Functions\nWorkflow")
        with Cluster("Lambdas"):
            validate = Lambda("Validate\nPolicy")
            canary = Lambda("Canary\nDeploy")
            monitor = Lambda("Monitor\nErrors")
            rollback = Lambda("Auto\nRollback")

        db = Dynamodb("Approvals\nTable")
        cw = Cloudwatch("CloudWatch\nAccessDenied\nMetrics")

    iam_roles = IdentityAndAccessManagementIam("Target IAM\nRoles")

    # Flow: CLI path
    user >> Edge(label="1") >> cli
    cli >> [cli_analyze, cli_propose, cli_apply]

    # AgentCore path
    user >> Edge(label="AgentCore\ninvoke", style="dashed") >> agentcore
    agentcore >> [action_analyze, action_guardrails]

    # Data collection
    cli_analyze >> Edge(label="--fast\n(default)") >> fast_collector >> cloudtrail
    cli_analyze >> Edge(label="--no-fast") >> analyzer_collector >> analyzer

    [fast_collector, analyzer_collector] >> Edge(label="usage\ndata") >> reasoning
    action_analyze >> Edge(label="CloudTrail") >> cloudtrail >> reasoning

    # AI reasoning
    reasoning >> bedrock_cluster
    bedrock_cluster >> [claude, nova]
    [claude, nova] >> Edge(label="rationale\nrisk score") >> guardrails

    # Policy processing
    guardrails >> diff_engine >> formatters
    action_guardrails >> Edge(label="sanitize") >> guardrails

    # Outputs
    formatters >> [s3_json, s3_cfn, s3_tf]
    cli_propose >> Edge(label="2") >> github

    # Rollout
    cli_apply >> Edge(label="3") >> stepfn
    stepfn >> validate >> canary >> monitor
    monitor >> Edge(label="errors?") >> rollback
    monitor >> Edge(label="success") >> iam_roles

    stepfn >> db
    monitor >> cw
    rollback >> Edge(label="revert", color="red") >> iam_roles
