# EKS デプロイ構成の刷新: cluster = AWS CDK / workload = Helm

## 背景

旧構成は eksctl の `ClusterConfig`(`k8s/cluster.yaml`)、生の Kubernetes
Manifest(`k8s/pod-deployment.yaml`)、単体の CloudFormation テンプレート
(`network/amazon-eks-vpc-private-subnets_without_nat.yaml`)がそれぞれ独立して
存在し、クラスタとワークロードの管理境界が曖昧だった。

本変更では以下の2層に責務を分離する。

| レイヤ | ツール | ディレクトリ |
| --- | --- | --- |
| クラスタ(VPC / EKSコントロールプレーン / Fargateプロファイル / OIDC・IRSA / AWS Load Balancer Controller) | AWS CDK (TypeScript) | `infra/cdk/` |
| ワークロード(Deployment / Service / Ingress / ServiceAccount) | Helm | `helm/flask-api/` |

削除したファイル: `k8s/`, `network/`(いずれも新構成に置き換え)。

## 設計判断

- **CDK 言語は TypeScript**: 当初は uv 管理の Python で実装していたが、CDK
  エコシステム(サンプル・L2コンストラクトのドキュメント量)との親和性を優先し
  TypeScript に切り替えた。CDK CLI 自体が npm 依存のため、ツールチェーンが
  npm ひとつに揃うメリットもある。Python 版との出力比較(`cdk synth` で得られる
  CloudFormation テンプレートのリソース構成が完全一致すること)は移行時に
  確認済み。
- **AWS Load Balancer Controller は CDK 側で導入**: IRSA ロールと Helm
  リリースが密結合するクラスタ必須アドオンのため、`cluster.addHelmChart()`
  で CDK が管理する。アプリケーション固有の Helm chart(`helm/flask-api`)とは
  別物。
- **アプリの IRSA ロールは CDK が作成、ServiceAccount は Helm が作成**: IAM
  Role(OIDC federated principal)は `infra/cdk/lib/eks-stack.ts` の
  `EksStack` が作成し、ARN を `AppServiceAccountRoleArn` の CFN Output で
  公開する。Kubernetes 側の `ServiceAccount` リソースは
  `helm/flask-api/templates/serviceaccount.yaml` が作成し、
  `serviceAccount.roleArn` value にそのARNを渡して
  `eks.amazonaws.com/role-arn` annotation を付与する。両者の所有者を CDK/Helm
  で完全に分離するための設計。
- **VPC はコンピュート方式を Fargate のまま維持**: 旧 `k8s/cluster.yaml` が
  `fargateProfiles` を使っていた構成を踏襲し、`eks.FargateCluster` を採用。
  ノードグループの運用(AMI更新・スケーリング等)が不要になる利点を維持。
- **NAT Gateway を追加**: 旧 CFN テンプレートはプライベートサブネットに
  デフォルトルートが無く(S3 Gateway Endpoint のみ)、ALB Controller や
  Fargate pod が ECR/DockerHub 等へ到達できない設計だった。運用の単純さを
  優先し NAT Gateway 1台を追加(`-c natGateways=0` で無効化可能)。
- **Bedrock 用 IAM ポリシー**: `flask-cloud-api-v2/modules/cloud3_bedrock.py`
  が `ChatBedrock` / `ChatBedrockConverse` で Bedrock を直接呼んでいるため、
  アプリ用 IRSA ロールに `bedrock:InvokeModel` 系のアクションを付与済み。

## デプロイ手順

### 1. クラスタ (CDK)

```fish
cd infra/cdk
nvm use 22.22.2
npm install
set -x CDK_DEFAULT_ACCOUNT (aws sts get-caller-identity --query Account --output text)
set -x CDK_DEFAULT_REGION ap-northeast-1
npx cdk bootstrap   # 初回のみ
npx cdk deploy --all
```

`FlaskApi-Eks-dev` スタックの Outputs に以下が出力される。

- `ConfigureKubectl`: kubeconfig 設定コマンド
- `AppServiceAccountRoleArn`: Helm chart に渡す IRSA ロール ARN

```fish
aws eks update-kubeconfig --name flask-api-dev --region ap-northeast-1
```

### 2. ワークロード (Helm)

```fish
helm upgrade --install flask-api helm/flask-api \
  --namespace flask-api --create-namespace \
  --set image.tag=<デプロイしたいイメージタグ> \
  --set serviceAccount.roleArn=<AppServiceAccountRoleArn の値>
```

ALB のホスト名が割り当たるまで待つ:

```fish
kubectl get ingress -n flask-api flask-api -w
```

## 環境を分ける場合

`bin/app.ts` は `-c envName=<name>` context でスタック名
(`FlaskApi-Network-<name>` / `FlaskApi-Eks-<name>`)とクラスタ名を切り替える。
Helm 側は `-n flask-api-<name>` 等でネームスペースを分け、release ごとに
`values-<env>.yaml` を用意する運用を想定。

## 未実施・要フォローアップ

- `infra/cdk` の `cdk deploy` はこのセッションでは AWS 認証セッション切れの
  ため実機検証できていない(オフラインで疑似 AZ コンテキストを与えた
  `cdk synth` によるロジック検証のみ実施、Python 版との出力一致も確認済み)。
  デプロイ前に認証を再取得のうえ `cdk diff` で確認すること。
- アプリ用 IRSA ロールの Bedrock 権限は `Resource: "*"` としている。必要で
  あれば利用モデル ARN 単位に絞り込みを検討。
