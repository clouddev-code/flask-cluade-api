#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.network_stack import NetworkStack
from stacks.eks_stack import EksStack

app = cdk.App()

env_name = app.node.try_get_context("envName") or "dev"
cluster_name = app.node.try_get_context("clusterName") or f"flask-api-{env_name}"

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "ap-northeast-1"),
)

tags = {
    "Project": "flask-cloud-api",
    "Environment": env_name,
    "ManagedBy": "aws-cdk",
}

network_stack = NetworkStack(
    app,
    f"FlaskApi-Network-{env_name}",
    env=env,
    tags=tags,
)

EksStack(
    app,
    f"FlaskApi-Eks-{env_name}",
    env=env,
    tags=tags,
    vpc=network_stack.vpc,
    cluster_name=cluster_name,
    env_name=env_name,
)

app.synth()
