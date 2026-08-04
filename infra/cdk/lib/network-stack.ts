import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import { Construct } from "constructs";

/**
 * VPC for the EKS cluster.
 *
 * Replaces the standalone network/amazon-eks-vpc-private-subnets_without_nat.yaml
 * CloudFormation template. Unlike the legacy template, this VPC ships with a NAT
 * gateway so private-subnet workloads (Fargate pods, the AWS Load Balancer
 * Controller) can reach ECR/DockerHub without needing a full set of interface
 * endpoints. Set context `natGateways=0` to go back to a no-NAT layout if the
 * endpoint-only cost tradeoff is preferred.
 */
export class NetworkStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const natGateways = Number(this.node.tryGetContext("natGateways") ?? 1);
    // Explicit AZs (matching the legacy eksctl config's ap-northeast-1a/1c
    // subnets) avoid a context-provider AZ lookup, which needs live AWS
    // credentials during `cdk synth`. Override with `-c availabilityZones=a,b`
    // when deploying to a different region.
    const availabilityZones: string[] = this.node.tryGetContext(
      "availabilityZones",
    ) ?? ["ap-northeast-1a", "ap-northeast-1c"];

    this.vpc = new ec2.Vpc(this, "Vpc", {
      availabilityZones,
      natGateways,
      subnetConfiguration: [
        {
          name: "Public",
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 20,
        },
        {
          name: "Private",
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 20,
        },
      ],
    });

    // Keep S3 pulls (e.g. EKS/ECR layer storage) off the NAT gateway.
    this.vpc.addGatewayEndpoint("S3Endpoint", {
      service: ec2.GatewayVpcEndpointAwsService.S3,
    });

    // NOTE: kubernetes.io/role/elb and kubernetes.io/role/internal-elb subnet
    // tags are applied automatically by the eks.Cluster construct in EksStack.
  }
}
