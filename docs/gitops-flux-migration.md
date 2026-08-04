# GitOps環境の導入: FluxCD

## 背景

`docs/eks-cdk-helm-migration.md` でクラスタ(CDK)とワークロード(Helm)の責務分離は
済んでいるが、デプロイ自体は `helm upgrade --install --set image.tag=...` を手元で
叩く手動運用で、CI(`.github/`)も存在しなかった。本変更で「Gitにpushしたら
ECRビルド→クラスタ反映まで自動で繋がる」GitOps環境を導入する。

## ツール選定

単一アプリ・Fargateのみ・マルチテナント予定なしという制約のもと、FluxCDを採用した。

| 選択肢 | 評価 |
| --- | --- |
| **FluxCD (採用)** | `HelmRelease` で既存の `helm/flask-api` chartをそのまま参照でき、pull型GitOpsを最小フットプリントで実現できる。Fargateのみの小規模クラスタに追加するcontroller数を絞りやすい。 |
| GitHub Actions push型 (`helm upgrade` を直接実行) | 学習コストは最小だが、狭義のGitOps(Git=単一の真実の源)にならない。 |
| ArgoCD | UI/可観測性は強いが、単一アプリ構成ではUI/Server/Repo-server等でPod数が過剰。マルチアプリ化が決まった時点で再検討。 |

## スコープ(段階分割)

- **フェーズ1(本変更)**: Flux本体 + `HelmRelease` によるGit→クラスタ反映のGitOps確立。
  イメージタグの更新は GitHub Actions が `clusters/dev/flask-api-helmrelease.yaml`
  を書き換えてcommitする方式(Flux自体はタグの出どころを知らない、単にGitの内容を
  反映するだけ)。
- **フェーズ2(未着手)**: Flux Image Automation Controller
  (`image-reflector-controller` + `image-automation-controller`)を導入し、
  ECRの新タグ検知→Git commitまでFlux側に持たせる。導入時は
  `image-reflector-controller` 用のIRSA(ECR read権限)と、タグの命名規則
  (時系列でソート可能な `sha-<shortsha>-<timestamp>` 等)の設計が必要。

## 構成

| レイヤ | 内容 | ディレクトリ |
| --- | --- | --- |
| クラスタ/CI用IAM | AppServiceAccountRoleに固定`roleName`を付与(FluxのHelmRelease valuesから決定論的にARNを参照できるようにするため)。GitHub Actions用OIDC Role(`FlaskApi-Ci`スタック、ECR push権限をmainブランチに限定して付与) | `infra/cdk/lib/eks-stack.ts`, `infra/cdk/lib/ci-stack.ts` |
| Flux管理マニフェスト | このリポジトリ自身を指す`GitRepository`と、`helm/flask-api`を参照する`HelmRelease` | `clusters/dev/` |
| CI | `flask-cloud-api-v2/**` の変更をトリガーにECRへbuild&push、`clusters/dev/flask-api-helmrelease.yaml`のタグを書き換えてcommit | `.github/workflows/build-and-push.yml` |

`clusters/dev/flux-system/` (bootstrap時にFlux CLIが生成するcontroller本体の
manifest群)はこのリポジトリにまだ存在しない。後述のbootstrap手順を実行すると
自動的に追加される。

## Bootstrap手順(初回のみ、実施者が手動で行う)

### 1. IAM Role をデプロイ

```fish
cd infra/cdk
nvm use 22.22.2
npx cdk deploy FlaskApi-Ci
```

Outputsの `GithubActionsEcrPushRoleArn` を、GitHubリポジトリの
**Settings > Secrets and variables > Actions > Variables** に
`AWS_ECR_PUSH_ROLE_ARN` として登録する。

### 2. GitHub Actions のワークフロー権限を設定

**Settings > Actions > General > Workflow permissions** を
「Read and write permissions」に変更する
(`build-and-push.yml` が `clusters/dev/flask-api-helmrelease.yaml` の
タグ更新をmainに直接commit/pushするため)。mainブランチにブランチ保護を
かけている場合は、Actions bot(`github-actions[bot]`)からの直接pushを
許可する例外設定が必要。

### 3. Flux CLI で bootstrap

```fish
brew install fluxcd/tap/flux
aws eks update-kubeconfig --name flask-api-dev --region ap-northeast-1
set -x GITHUB_TOKEN (gh auth token)
flux bootstrap github \
  --owner=clouddev-code \
  --repository=flask-cluade-api \
  --branch=main \
  --path=clusters/dev \
  --personal
```

これにより `clusters/dev/flux-system/` が生成され、mainにcommitされる。
以降、Flux自身の更新もGitOps(このリポジトリへのcommit)で行われる。

### 4. 反映確認

```fish
flux get sources git
flux get helmreleases -A
kubectl get pods -n flask-api
```

## 運用フロー(フェーズ1)

1. `flask-cloud-api-v2/` を変更してmainにpush
2. `build-and-push.yml` がECRへイメージをbuild&push(タグ=short SHA)
3. 同ワークフローが `clusters/dev/flask-api-helmrelease.yaml` の
   `spec.values.image.tag` を書き換えてcommit/push
4. Fluxの `source-controller` が新しいcommitを検知(最大5分、`GitRepository`の
   `interval`)
5. `helm-controller` が `HelmRelease` を再reconcileし、`helm upgrade` が
   実行される

`docs/eks-cdk-helm-migration.md` に記載していた手動 `helm upgrade --install`
手順は、Flux導入後は不要になる(緊急時の切り離し用に残すことは可能)。
