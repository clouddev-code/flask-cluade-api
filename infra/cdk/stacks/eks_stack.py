import json
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_eks as eks
from aws_cdk import aws_iam as iam
from aws_cdk.lambda_layer_kubectl_v31 import KubectlV31Layer
from constructs import Construct

ALB_CONTROLLER_POLICY_PATH = (
    Path(__file__).parent / "aws_load_balancer_controller_iam_policy.json"
)

APP_NAMESPACE = "flask-api"
APP_SERVICE_ACCOUNT_NAME = "flask-api"


class EksStack(cdk.Stack):
    """EKS cluster (control plane + Fargate compute + cluster-level add-ons).

    Scope: everything the cluster needs to be ready for a `helm install` --
    VPC wiring, OIDC/IRSA, Fargate profiles, and the AWS Load Balancer
    Controller (a platform add-on, not application workload). The actual
    application Deployment/Service/Ingress/ServiceAccount live in
    helm/flask-api and are deployed independently with `helm upgrade --install`.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.IVpc,
        cluster_name: str,
        env_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cluster = eks.FargateCluster(
            self,
            "Cluster",
            cluster_name=cluster_name,
            vpc=vpc,
            vpc_subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)],
            version=eks.KubernetesVersion.V1_31,
            kubectl_layer=KubectlV31Layer(self, "KubectlLayer"),
            endpoint_access=eks.EndpointAccess.PUBLIC_AND_PRIVATE,
            cluster_logging=[
                eks.ClusterLoggingTypes.API,
                eks.ClusterLoggingTypes.AUDIT,
                eks.ClusterLoggingTypes.AUTHENTICATOR,
            ],
        )
        self.cluster = cluster

        # Fargate profile for the application namespace. The FargateCluster
        # construct already ships a default profile covering `default` and
        # `kube-system`, which is where the ALB controller below lands.
        cluster.add_fargate_profile(
            "AppFargateProfile",
            selectors=[eks.Selector(namespace=APP_NAMESPACE)],
        )

        self._add_aws_load_balancer_controller(cluster)
        self.app_service_account_role = self._add_app_irsa_role(cluster)

        cdk.CfnOutput(self, "ClusterName", value=cluster.cluster_name)
        cdk.CfnOutput(self, "ClusterEndpoint", value=cluster.cluster_endpoint)
        cdk.CfnOutput(
            self,
            "ConfigureKubectl",
            value=f"aws eks update-kubeconfig --name {cluster.cluster_name} --region {self.region}",
        )
        cdk.CfnOutput(
            self,
            "AppServiceAccountRoleArn",
            value=self.app_service_account_role.role_arn,
            description=(
                "Pass to the Helm chart as serviceAccount.roleArn "
                f"(namespace={APP_NAMESPACE}, name={APP_SERVICE_ACCOUNT_NAME})"
            ),
        )

    def _add_aws_load_balancer_controller(self, cluster: eks.FargateCluster) -> None:
        alb_service_account = cluster.add_service_account(
            "AlbControllerServiceAccount",
            name="aws-load-balancer-controller",
            namespace="kube-system",
        )

        policy_document = json.loads(ALB_CONTROLLER_POLICY_PATH.read_text())
        for statement in policy_document["Statement"]:
            alb_service_account.add_to_principal_policy(
                iam.PolicyStatement.from_json(statement)
            )

        cluster.add_helm_chart(
            "AwsLoadBalancerController",
            chart="aws-load-balancer-controller",
            repository="https://aws.github.io/eks-charts",
            namespace="kube-system",
            version="1.11.0",
            values={
                "clusterName": cluster.cluster_name,
                "region": self.region,
                "vpcId": cluster.vpc.vpc_id,
                "serviceAccount": {
                    "create": False,
                    "name": alb_service_account.service_account_name,
                },
            },
        )

    def _add_app_irsa_role(self, cluster: eks.FargateCluster) -> iam.Role:
        """IAM role for the app's ServiceAccount.

        The ServiceAccount object itself is created by the Helm chart
        (helm/flask-api), not here -- only the IRSA trust role is
        cluster-managed. The Helm chart's serviceAccount.roleArn value must
        be set to this role's ARN (see the AppServiceAccountRoleArn output).
        """
        oidc_provider = cluster.open_id_connect_provider
        sub_condition_key = f"{oidc_provider.open_id_connect_provider_issuer}:sub"
        aud_condition_key = f"{oidc_provider.open_id_connect_provider_issuer}:aud"

        # The issuer (and thus the condition key) is only known at deploy time,
        # so the condition map itself has to be resolved via CfnJson rather than
        # a plain Python dict.
        string_conditions = cdk.CfnJson(
            self,
            "AppServiceAccountConditions",
            value={
                sub_condition_key: f"system:serviceaccount:{APP_NAMESPACE}:{APP_SERVICE_ACCOUNT_NAME}",
                aud_condition_key: "sts.amazonaws.com",
            },
        )

        role = iam.Role(
            self,
            "AppServiceAccountRole",
            assumed_by=iam.FederatedPrincipal(
                oidc_provider.open_id_connect_provider_arn,
                conditions={"StringEquals": string_conditions},
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
            description="IRSA role assumed by the flask-api workload ServiceAccount (Helm-managed)",
        )

        # flask-cloud-api-v2/modules/cloud3_bedrock.py invokes Bedrock models
        # (ChatBedrock / ChatBedrockConverse) directly from the pod.
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:Converse",
                    "bedrock:ConverseStream",
                ],
                resources=["*"],
            )
        )

        return role
