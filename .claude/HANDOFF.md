# HANDOFF — EKS cluster(CDK) / workload(Helm) 移行 → GitOps(FluxCD)導入

最終更新: このセッション時点（コンテキスト圧縮前の保存）

## ブランチ / PR

- ブランチ: `infra/eks-cdk-helm`（`main` から分岐）
- PR: https://github.com/clouddev-code/flask-cluade-api/pull/10 （説明追記済み）
- コミット:
  - `08855f9` EKSデプロイをクラスタ=AWS CDK / ワークロード=Helmに再構成（初期実装、当初CDKはPython）
  - `c330c75` infra/cdk を Python から TypeScript に移行（最新の"確定"コミット）
- 上記2コミットは push 済み。**今回のGitOps(FluxCD)関連の変更は未commit**（下記参照、作業ツリーに存在）。

## やったこと（完了）

1. **役割分担**: クラスタ(VPC/EKSコントロールプレーン/Fargateプロファイル/OIDC・IRSA/AWS Load Balancer Controller) = AWS CDK、ワークロード(Deployment/Service/Ingress/ServiceAccount) = Helm chart、に分離。
2. **`infra/cdk/`**（CDK, **TypeScript**。当初Pythonで実装したが、ユーザー指示によりTSへ全面書き換え済み）
   - `bin/app.ts`: エントリポイント。`-c envName=<name>` でスタック名/クラスタ名を切替（デフォルト `dev`）
   - `lib/network-stack.ts`: VPC（ap-northeast-1a/1c 固定AZ、NAT Gateway 1台、S3 Gateway Endpoint）
   - `lib/eks-stack.ts`: `eks.FargateCluster`（K8s 1.31、`KubectlV31Layer`）、Fargateプロファイル追加（namespace `flask-api`）、AWS Load Balancer Controllerを`addHelmChart`でCDK側から導入、アプリ用IRSA IAMロール（`system:serviceaccount:flask-api:flask-api` にfederated trust、Bedrock invoke権限付与）、CfnOutputで`ClusterName`/`ClusterEndpoint`/`ConfigureKubectl`/`AppServiceAccountRoleArn`を出力
   - `lib/aws-load-balancer-controller-iam-policy.json`: AWS公式ポリシーをそのままダウンロードして使用
   - 依存: `aws-cdk-lib@2.263.0`, `@aws-cdk/lambda-layer-kubectl-v31@^2.1.0`, TypeScript ~5.6.3
3. **`helm/flask-api/`**（Helm chart）
   - Deployment/Service(ClusterIP)/Ingress(ALB, ingressClassName: alb)/ServiceAccount
   - `values.yaml` の `serviceAccount.roleArn` にCDKの`AppServiceAccountRoleArn`出力値を渡す設計（CDK=IAM Role作成、Helm=K8s ServiceAccountオブジェクト作成、で所有者を分離）
   - `fullnameOverride: "flask-api"` 固定
4. **削除**: 旧 `k8s/`（eksctl ClusterConfig、生Manifest、誤ってコミットされていたkubectlバイナリ）、`network/`（単体CFNテンプレート）
5. **ドキュメント**: `docs/eks-cdk-helm-migration.md`（設計判断・デプロイ手順を詳述、TS移行後の内容に更新済み）、`infra/cdk/README.md`
6. **検証**（すべてこのセッション内、AWS認証なしで実施）
   - `helm lint` / `helm template` パス
   - TypeScript版: `npx tsc --noEmit` パス、`cdk synth` をオフライン（`cdk.context.json` に疑似AZリストを手動投入）で実行し成功、Python版と生成CloudFormationテンプレートのリソース構成（31リソース）が完全一致することを確認
   - `npm audit`: `aws-cdk-lib` バンドル内 `brace-expansion` の高深刻度CVEあり。修正版未公開・CDK CLI自体が抱える既知の依存のため対応不可（許容）

## 重要な設計判断（Advisor(fable)にも確認済み）

- ALB Controllerなど「クラスタが機能するための必須アドオン」はCDK側で導入。アプリ固有Helm chartとは分離。
- アプリ用ServiceAccountのIRSA IAM RoleはCDKが作成、K8s ServiceAccountオブジェクト自体はHelmが作成（ARNをvaluesで橋渡し）。
- Compute方式は旧構成(eksctl fargateProfiles)を踏襲しFargateのまま。
- 旧CFNテンプレートにはプライベートサブネットの外向きルートが無かったため、NAT Gateway 1台を追加（`-c natGateways=0`で無効化可）。
- CDK言語は当初Python(uv)を選んだが、**ユーザー指示によりTypeScriptへ移行**（エコシステム親和性を優先）。

## 未実施 / 要フォローアップ（次のセッションでやるべきこと）

- **実AWSアカウントでの検証が未実施**: このセッションではAWS SSOセッションが切れていた（`~/.aws/config` の default profile は `us-west-2` / SSO role）。認証を再取得のうえ `cd infra/cdk && npx cdk diff` → `npx cdk deploy --all` → `helm upgrade --install` の一連の動作確認が必要。
- アプリ用IRSAロールのBedrock権限は `Resource: "*"`。必要なら利用モデルARN単位に絞り込み検討。
- PRのマージ前レビュー・実機テストはまだ。

## 今回のセッションで追加: GitOps(FluxCD)導入 — 未commit

ユーザーから「GitOps環境を検討したい」という依頼。Advisor(fable)にツール選定
（FluxCD vs ArgoCD vs GitHub Actions push型）を確認 → **FluxCD採用**（単一アプリ
・Fargateのみ・マルチテナント予定なしのため最小フットプリント）。ユーザーに
AskUserQuestionでスコープ確認済み: (1)イメージタグ自動化は**段階分割**（Image
Automation Controllerは次フェーズ、今回はGitHub Actionsがvalues書き換えて
commitする方式）、(2)Fluxマニフェストは**このリポジトリ内**(`clusters/dev/`)、
(3)CI(GitHub Actions)は**今回新設する**。詳細設計は `docs/gitops-flux-migration.md`
に記載済み。

### 変更ファイル（すべて未commit、作業ツリーに存在）

- `infra/cdk/lib/eks-stack.ts`: `AppServiceAccountRole` に固定`roleName`
  (`flask-api-<envName>-app`)を付与。FluxのHelmRelease valuesからARNを
  決定論的に参照できるようにするための変更（CDK deploy後の手動コピペを廃止）。
- `infra/cdk/lib/ci-stack.ts`(新規): GitHub Actions OIDC role
  (`flask-api-github-actions-ecr-push`)。`clouddev-code/flask-cluade-api`の
  mainブランチからのAssumeRoleWithWebIdentityのみ許可、ECR repo
  `flasksample`へのpush権限を付与。
- `infra/cdk/bin/app.ts`: `CiStack`(`FlaskApi-Ci`)を追加登録。
- `clusters/dev/gitrepository.yaml`(新規): このリポジトリ自身を指す
  `GitRepository`。
- `clusters/dev/flask-api-helmrelease.yaml`(新規): `helm/flask-api`を参照する
  `HelmRelease`。`values.serviceAccount.roleArn`は
  `arn:aws:iam::905860205176:role/flask-api-dev-app`をハードコード
  （固定roleName前提）。`values.image.tag`はCIが書き換える対象。
  ※`clusters/dev/flux-system/`はまだ存在しない。`flux bootstrap`実行時に生成される。
- `.github/workflows/build-and-push.yml`(新規): `flask-cloud-api-v2/**`への
  push(main)をトリガーにECR build&push(タグ=short SHA)→
  `clusters/dev/flask-api-helmrelease.yaml`のタグを書き換えてcommit/push。
- `docs/gitops-flux-migration.md`(新規): 設計判断・bootstrap手順・運用フローの詳細。
- `docs/eks-cdk-helm-migration.md`, `infra/cdk/README.md`: FluxCD導入への
  言及を追記（既存の手動`helm upgrade`手順は初回確認・緊急時用として残置）。

### 検証済み（すべてAWS認証なしで実施）

- `npx tsc --noEmit` パス。
- `cdk synth FlaskApi-Ci` / `cdk synth FlaskApi-Eks-dev`（それぞれ単体で指定）
  はオフラインで成功。ECR ARNが`ap-northeast-1`で正しく解決されることを確認
  （※ローカル環境の`~/.aws/config`デフォルトが`us-west-2`のため、`AWS_REGION`
  /`AWS_DEFAULT_REGION`を明示的にoverrideする必要があった。cdk CLIが
  `CDK_DEFAULT_REGION`をSDK解決値で上書きする挙動によるもの、コード側の問題ではない）。
- **既知の事象（今回の変更とは無関係）**: `npx cdk synth`(スタック名なし=全スタック
  一括)は`FlaskApi-Network-dev`で「AWS認証が必要」エラーになる。これは
  `c330c75`時点のベースラインでも再現することを確認済み（git stashで検証）。
  スタック名を指定した個別synthでは問題ない。実機デプロイ時は認証があるため
  影響しない想定。
- `helm lint` / `helm template`（`serviceAccount.roleArn`をCLIで注入）パス。
- `clusters/dev/*.yaml`, `.github/workflows/build-and-push.yml` はYAML構文チェック済み
  （`kubectl apply --dry-run`はローカルkubeconfigが別プロジェクトのGKEを向いていて
  実行不可だったため、PyYAMLでの構文パースのみ）。

### 次セッションでやるべきこと

- 上記変更をcommit（まだ未commit）。
- **実アカウントでの`flux bootstrap`は未実施**。手順は
  `docs/gitops-flux-migration.md`の「Bootstrap手順」参照。実施には
  (1) `cdk deploy FlaskApi-Ci`→ `AWS_ECR_PUSH_ROLE_ARN`をGitHub repo variable
  に設定、(2) GitHub Actions workflow permissionsを"Read and write"に変更、
  (3) `flux bootstrap github --owner=clouddev-code --repository=flask-cluade-api
  --branch=main --path=clusters/dev --personal` の実行が必要（すべてAWS/GitHub
  認証必須、このセッションでは実行していない）。
- Image Automation Controller導入（フェーズ2、`docs/gitops-flux-migration.md`の
  「スコープ」参照）は未着手。
- ブランチ保護でActions botからのmain直push（タグbumpコミット）が許可されているか
  未確認。ブロックされる場合はワークフロー側をPR作成方式に変更する必要あり。

## 触っていないもの（他タスクの未関連な変更、このセッションでは一切手を加えていない）

- `frontend/` 配下の削除、`cloudeploy.yaml`/`run-dev.yaml`/`skaffold.yaml`/`requirements.txt`/`test` の削除、`flask-cloud-api-v2/` 内の変更（`cloud3_vertexai.py`, `gemini_vertexai.py`, `app.py`, `pyproject.toml`, `uv.lock` 等）、`flask-cloud-api-v2/modules/aws_knowledge.py` / `session_store.py` の新規ファイル、`docs/` 配下のCloud Run/IAP関連ドキュメント群。
  → これらは元々ワーキングツリーに存在した未コミットの変更で、ユーザーの別作業と思われるため未着手のまま。次セッションで触る場合はユーザーに確認すること。
