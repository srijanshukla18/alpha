#!/usr/bin/env python3
"""
AWS CDK application for deploying the ALPHA agent infrastructure.
"""
import os

import aws_cdk as cdk

from lib.alpha_stack import AlphaStack

app = cdk.App()

AlphaStack(
    app,
    "AlphaStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION", "us-east-1"),
    ),
    description="ALPHA - Autonomous Least-Privilege Hardening Agent",
)

app.synth()
