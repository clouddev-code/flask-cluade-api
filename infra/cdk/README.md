# infra/cdk

AWS CDK (Python) app that provisions the EKS cluster for flask-cloud-api-v2:
VPC, EKS control plane, Fargate profiles, OIDC/IRSA, and the AWS Load
Balancer Controller. Application workload (Deployment/Service/Ingress) is
deployed separately via the Helm chart in `helm/flask-api`.

See `docs/eks-cdk-helm-migration.md` at the repo root for the full design
notes and deploy steps.

## Quick start

```fish
uv sync
set -x CDK_DEFAULT_ACCOUNT (aws sts get-caller-identity --query Account --output text)
set -x CDK_DEFAULT_REGION ap-northeast-1
uv run cdk diff
uv run cdk deploy --all
```

## Layout

- `app.py` — CDK App entrypoint, wires `NetworkStack` -> `EksStack`
- `stacks/network_stack.py` — VPC (public/private subnets, NAT gateway, S3 gateway endpoint)
- `stacks/eks_stack.py` — Fargate EKS cluster, Fargate profiles, AWS Load Balancer Controller, app IRSA role
