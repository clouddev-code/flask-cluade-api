import * as cdk from "aws-cdk-lib";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as iam from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";

const GITHUB_OIDC_PROVIDER_HOST = "token.actions.githubusercontent.com";
const GITHUB_REPO = "clouddev-code/flask-cluade-api";
const ECR_REPOSITORY_NAME = "flasksample";

/**
 * IAM role that this repo's GitHub Actions workflows assume via OIDC to
 * build and push images to the pre-existing ECR repository. Kept separate
 * from EksStack: this role has nothing to do with the cluster and is used
 * only by CI running outside it.
 */
export class CiStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // An AWS account only ever needs one OIDC provider per issuer URL. If
    // `cdk deploy` fails with "already exists" here, this repo's account
    // already trusts GitHub Actions -- replace this with
    // `iam.OpenIdConnectProvider.fromOpenIdConnectProviderArn(...)` using
    // the existing provider's ARN instead of creating a new one.
    const githubOidcProvider = new iam.OpenIdConnectProvider(
      this,
      "GithubOidcProvider",
      {
        url: `https://${GITHUB_OIDC_PROVIDER_HOST}`,
        clientIds: ["sts.amazonaws.com"],
      },
    );

    const ecrRepository = ecr.Repository.fromRepositoryName(
      this,
      "AppEcrRepository",
      ECR_REPOSITORY_NAME,
    );

    const role = new iam.Role(this, "GithubActionsEcrPushRole", {
      roleName: "flask-api-github-actions-ecr-push",
      assumedBy: new iam.FederatedPrincipal(
        githubOidcProvider.openIdConnectProviderArn,
        {
          StringEquals: {
            [`${GITHUB_OIDC_PROVIDER_HOST}:aud`]: "sts.amazonaws.com",
          },
          // Restrict to the main branch only -- this role can push images
          // and commit tag bumps back to the repo, so PR/fork builds must
          // not be able to assume it.
          StringLike: {
            [`${GITHUB_OIDC_PROVIDER_HOST}:sub`]: `repo:${GITHUB_REPO}:ref:refs/heads/main`,
          },
        },
        "sts:AssumeRoleWithWebIdentity",
      ),
      description:
        "Assumed by GitHub Actions (main branch only) to build and push flask-cloud-api-v2 images to ECR",
    });

    // GetAuthorizationToken is account/region-scoped (no repository ARN to
    // grant against), so it's added separately from grantPullPush below.
    role.addToPolicy(
      new iam.PolicyStatement({
        actions: ["ecr:GetAuthorizationToken"],
        resources: ["*"],
      }),
    );
    ecrRepository.grantPullPush(role);

    new cdk.CfnOutput(this, "GithubActionsEcrPushRoleArn", {
      value: role.roleArn,
      description:
        "Set as the AWS_ECR_PUSH_ROLE_ARN GitHub Actions repository variable",
    });
  }
}
