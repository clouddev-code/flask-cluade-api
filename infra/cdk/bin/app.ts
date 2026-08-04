#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { NetworkStack } from "../lib/network-stack";
import { EksStack } from "../lib/eks-stack";

const app = new cdk.App();

const envName = (app.node.tryGetContext("envName") as string) ?? "dev";
const clusterName =
  (app.node.tryGetContext("clusterName") as string) ?? `flask-api-${envName}`;

const env: cdk.Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION ?? "ap-northeast-1",
};

const tags = {
  Project: "flask-cloud-api",
  Environment: envName,
  ManagedBy: "aws-cdk",
};

const networkStack = new NetworkStack(app, `FlaskApi-Network-${envName}`, {
  env,
  tags,
});

new EksStack(app, `FlaskApi-Eks-${envName}`, {
  env,
  tags,
  vpc: networkStack.vpc,
  clusterName,
  envName,
});

app.synth();
