#!/usr/bin/env python3
"""
ALPHA - Simple Architecture Diagram
Generates: alpha_architecture_simple.png
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
from diagrams.onprem.vcs import Github
from diagrams.onprem.client import User

graph_attr = {
    "fontsize": "16",
    "bgcolor": "white",
    "pad": "0.5",
}

with Diagram("ALPHA - Autonomous Least-Privilege Hardening Agent",
             show=False,
             direction="LR",
             graph_attr=graph_attr,
             filename="alpha_architecture_simple"):

    user = User("Developer")

    with Cluster("ALPHA CLI"):
        cli = Lambda("alpha analyze\nalpha propose\nalpha apply")

    with Cluster("Data Collection"):
        cloudtrail = Cloudtrail("CloudTrail\nEvent History")
        analyzer = IAMAccessAnalyzer("Access Analyzer\n(optional)")

    with Cluster("AI Reasoning"):
        bedrock = Bedrock("Bedrock\n(Claude/Nova)")
        agentcore = Lambda("AgentCore\nRuntime")

    with Cluster("Policy Enforcement"):
        guardrails = IdentityAndAccessManagementIam("Guardrails\nPresets")
        iam = IdentityAndAccessManagementIam("IAM Roles")

    with Cluster("Deployment"):
        stepfn = StepFunctions("Step Functions\nCanary Rollout")
        db = Dynamodb("Approvals")
        cw = Cloudwatch("Monitoring")

    outputs = [
        S3("S3\nProposal JSON"),
        Github("GitHub\nPR")
    ]

    # Flow
    user >> Edge(label="1. analyze") >> cli
    cli >> Edge(label="Fast mode") >> cloudtrail
    cli >> Edge(label="Analyzer mode") >> analyzer

    [cloudtrail, analyzer] >> Edge(label="usage data") >> agentcore
    agentcore >> Edge(label="reason") >> bedrock
    bedrock >> Edge(label="proposal") >> guardrails

    guardrails >> Edge(label="sanitized\npolicy") >> outputs
    guardrails >> Edge(label="3. apply") >> stepfn

    stepfn >> [db, cw]
    stepfn >> Edge(label="canary\nrollout") >> iam
