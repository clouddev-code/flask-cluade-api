import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class NetworkStack(cdk.Stack):
    """VPC for the EKS cluster.

    Replaces the standalone network/amazon-eks-vpc-private-subnets_without_nat.yaml
    CloudFormation template. Unlike the legacy template, this VPC ships with a NAT
    gateway so private-subnet workloads (Fargate pods, the AWS Load Balancer
    Controller) can reach ECR/DockerHub without needing a full set of interface
    endpoints. Set context `natGateways=0` to go back to a no-NAT layout if the
    endpoint-only cost tradeoff is preferred.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        nat_gateways = int(self.node.try_get_context("natGateways") or 1)
        # Explicit AZs (matching the legacy eksctl config's ap-northeast-1a/1c
        # subnets) avoid a context-provider AZ lookup, which needs live AWS
        # credentials during `cdk synth`. Override with `-c availabilityZones=a,b`
        # when deploying to a different region.
        availability_zones = (
            self.node.try_get_context("availabilityZones")
            or ["ap-northeast-1a", "ap-northeast-1c"]
        )

        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            availability_zones=availability_zones,
            nat_gateways=nat_gateways,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=20,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=20,
                ),
            ],
        )

        # Keep S3 pulls (e.g. EKS/ECR layer storage) off the NAT gateway.
        self.vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )

        # NOTE: kubernetes.io/role/elb and kubernetes.io/role/internal-elb subnet
        # tags are applied automatically by the eks.Cluster construct in EksStack.
