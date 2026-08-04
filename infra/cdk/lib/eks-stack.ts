import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as eks from "aws-cdk-lib/aws-eks";
import * as iam from "aws-cdk-lib/aws-iam";
import { KubectlV31Layer } from "@aws-cdk/lambda-layer-kubectl-v31";
import { Construct } from "constructs";
import albControllerPolicy from "./aws-load-balancer-controller-iam-policy.json";

const APP_NAMESPACE = "flask-api";
const APP_SERVICE_ACCOUNT_NAME = "flask-api";

export interface EksStackProps extends cdk.StackProps {
  readonly vpc: ec2.IVpc;
  readonly clusterName: string;
  readonly envName: string;
}

/**
 * EKS cluster (control plane + Fargate compute + cluster-level add-ons).
 *
 * Scope: everything the cluster needs to be ready for a `helm install` --
 * VPC wiring, OIDC/IRSA, Fargate profiles, and the AWS Load Balancer
 * Controller (a platform add-on, not application workload). The actual
 * application Deployment/Service/Ingress/ServiceAccount live in
 * helm/flask-api and are deployed independently with `helm upgrade --install`.
 */
export class EksStack extends cdk.Stack {
  public readonly cluster: eks.FargateCluster;
  public readonly appServiceAccountRole: iam.Role;

  constructor(scope: Construct, id: string, props: EksStackProps) {
    super(scope, id, props);

    const cluster = new eks.FargateCluster(this, "Cluster", {
      clusterName: props.clusterName,
      vpc: props.vpc,
      vpcSubnets: [{ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }],
      version: eks.KubernetesVersion.V1_31,
      kubectlLayer: new KubectlV31Layer(this, "KubectlLayer"),
      endpointAccess: eks.EndpointAccess.PUBLIC_AND_PRIVATE,
      clusterLogging: [
        eks.ClusterLoggingTypes.API,
        eks.ClusterLoggingTypes.AUDIT,
        eks.ClusterLoggingTypes.AUTHENTICATOR,
      ],
    });
    this.cluster = cluster;

    // Fargate profile for the application namespace. The FargateCluster
    // construct already ships a default profile covering `default` and
    // `kube-system`, which is where the ALB controller below lands.
    cluster.addFargateProfile("AppFargateProfile", {
      selectors: [{ namespace: APP_NAMESPACE }],
    });

    this.addAwsLoadBalancerController(cluster);
    this.appServiceAccountRole = this.addAppIrsaRole(cluster);

    new cdk.CfnOutput(this, "ClusterName", { value: cluster.clusterName });
    new cdk.CfnOutput(this, "ClusterEndpoint", {
      value: cluster.clusterEndpoint,
    });
    new cdk.CfnOutput(this, "ConfigureKubectl", {
      value: `aws eks update-kubeconfig --name ${cluster.clusterName} --region ${this.region}`,
    });
    new cdk.CfnOutput(this, "AppServiceAccountRoleArn", {
      value: this.appServiceAccountRole.roleArn,
      description:
        "Pass to the Helm chart as serviceAccount.roleArn " +
        `(namespace=${APP_NAMESPACE}, name=${APP_SERVICE_ACCOUNT_NAME})`,
    });
  }

  private addAwsLoadBalancerController(cluster: eks.FargateCluster): void {
    const albServiceAccount = cluster.addServiceAccount(
      "AlbControllerServiceAccount",
      {
        name: "aws-load-balancer-controller",
        namespace: "kube-system",
      },
    );

    for (const statement of albControllerPolicy.Statement) {
      albServiceAccount.addToPrincipalPolicy(
        iam.PolicyStatement.fromJson(statement),
      );
    }

    cluster.addHelmChart("AwsLoadBalancerController", {
      chart: "aws-load-balancer-controller",
      repository: "https://aws.github.io/eks-charts",
      namespace: "kube-system",
      version: "1.11.0",
      values: {
        clusterName: cluster.clusterName,
        region: this.region,
        vpcId: cluster.vpc.vpcId,
        serviceAccount: {
          create: false,
          name: albServiceAccount.serviceAccountName,
        },
      },
    });
  }

  /**
   * IAM role for the app's ServiceAccount.
   *
   * The ServiceAccount object itself is created by the Helm chart
   * (helm/flask-api), not here -- only the IRSA trust role is
   * cluster-managed. The Helm chart's serviceAccount.roleArn value must
   * be set to this role's ARN (see the AppServiceAccountRoleArn output).
   */
  private addAppIrsaRole(cluster: eks.FargateCluster): iam.Role {
    const oidcProvider = cluster.openIdConnectProvider;
    const subConditionKey = `${oidcProvider.openIdConnectProviderIssuer}:sub`;
    const audConditionKey = `${oidcProvider.openIdConnectProviderIssuer}:aud`;

    // The issuer (and thus the condition key) is only known at deploy time,
    // so the condition map itself has to be resolved via CfnJson rather than
    // a plain object literal.
    const stringConditions = new cdk.CfnJson(
      this,
      "AppServiceAccountConditions",
      {
        value: {
          [subConditionKey]: `system:serviceaccount:${APP_NAMESPACE}:${APP_SERVICE_ACCOUNT_NAME}`,
          [audConditionKey]: "sts.amazonaws.com",
        },
      },
    );

    const role = new iam.Role(this, "AppServiceAccountRole", {
      assumedBy: new iam.FederatedPrincipal(
        oidcProvider.openIdConnectProviderArn,
        { StringEquals: stringConditions },
        "sts:AssumeRoleWithWebIdentity",
      ),
      description:
        "IRSA role assumed by the flask-api workload ServiceAccount (Helm-managed)",
    });

    // flask-cloud-api-v2/modules/cloud3_bedrock.py invokes Bedrock models
    // (ChatBedrock / ChatBedrockConverse) directly from the pod.
    role.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:Converse",
          "bedrock:ConverseStream",
        ],
        resources: ["*"],
      }),
    );

    return role;
  }
}
