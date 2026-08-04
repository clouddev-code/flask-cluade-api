# infra/cdk

AWS CDK (TypeScript) app that provisions the EKS cluster for
flask-cloud-api-v2: VPC, EKS control plane, Fargate profiles, OIDC/IRSA, and
the AWS Load Balancer Controller. Application workload
(Deployment/Service/Ingress) is deployed separately via the Helm chart in
`helm/flask-api`, kept in sync with the cluster by FluxCD (see
`clusters/dev/`). It also provisions the GitHub Actions OIDC role used to
build and push images to ECR (`CiStack`).

See `docs/eks-cdk-helm-migration.md` and `docs/gitops-flux-migration.md` at
the repo root for the full design notes and deploy steps.

## Quick start

```fish
nvm use 22.22.2
npm install
set -x CDK_DEFAULT_ACCOUNT (aws sts get-caller-identity --query Account --output text)
set -x CDK_DEFAULT_REGION ap-northeast-1
npx cdk diff
npx cdk deploy --all
```

## Layout

- `bin/app.ts` — CDK App entrypoint, wires `NetworkStack` -> `EksStack`, plus the standalone `CiStack`
- `lib/network-stack.ts` — VPC (public/private subnets, NAT gateway, S3 gateway endpoint)
- `lib/eks-stack.ts` — Fargate EKS cluster, Fargate profiles, AWS Load Balancer Controller, app IRSA role
- `lib/ci-stack.ts` — GitHub Actions OIDC role scoped to pushing images to the `flasksample` ECR repo
- `lib/aws-load-balancer-controller-iam-policy.json` — official upstream IAM policy for the ALB controller
