# Next.js SSR (Firebase App Hosting) + IAP 保護 Cloud Run アクセス設計

## 1. 結論サマリ

| 項目 | 内容 |
| --- | --- |
| 配信 | **Firebase App Hosting**（Next.js SSR を内部で Cloud Run 上で動かす） |
| BFF | Next.js の **Route Handlers**（`app/api/qs/[...path]/route.ts`）が同一プロセスで担う |
| 認証トークン | App Hosting バックエンドの **ランタイムサービスアカウント**で audience 付き OIDC ID トークン発行 |
| frontend | `/api/qs/...` を相対パスで叩くだけ。**同一オリジン**なので CORS なし |
| `output: 'export'` | **削除する**（静的書き出しを止める） |

```
[Browser] ── /api/qs/...（相対パス）─▶ [Firebase App Hosting]
                                       └─ Next.js SSR (Cloud Run 内部)
                                              │ Authorization: Bearer <ID_TOKEN>
                                              │ audience = IAP OAuth Client ID
                                              ▼
                                          [IAP] ──▶ [deploy-qs-dev]
```

---

## 2. 前提情報の収集

### 2.1 IAP の OAuth Client ID
```bash
PROJECT_ID="<your-project-id>"
gcloud iap oauth-brands list --project=$PROJECT_ID
gcloud iap oauth-clients list <BRAND_NAME> --project=$PROJECT_ID
```
取得した値をメモ:
```
IAP_AUDIENCE=<NUMBER>-<HASH>.apps.googleusercontent.com
DEPLOY_QS_BASE_URL=https://deploy-qs-dev-xxxxxxxx.<region>.run.app
```

### 2.2 Firebase App Hosting のランタイム SA
App Hosting バックエンドを作成すると、デフォルトで以下の SA がランタイムとして割り当てられます:
```
firebase-app-hosting-compute@<PROJECT_ID>.iam.gserviceaccount.com
```
（任意の SA に差し替えも可能。`apphosting.yaml` の `runConfig.serviceAccount`）

この SA に IAP 越しアクセスを許可:
```bash
SA="firebase-app-hosting-compute@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA}" \
  --role="roles/iap.httpsResourceAccessor"

# IAP Console → 対象 Cloud Run → 「メンバーを追加」で上記 SA を登録（GUI が必要なケースあり）
```

---

## 3. Next.js 側の変更

### 3.1 `next.config.ts` から static export を外す

```ts
// frontend/next.config.ts
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  // output: 'export',  ← 削除
  // 必要なら以下を追加
  experimental: {
    serverActions: { allowedOrigins: [] },
  },
}

export default nextConfig
```

合わせて掃除:
```bash
cd frontend
rm -rf out
# package.json の serve/deploy スクリプトは App Hosting 用に書き換え（後述）
```

### 3.2 依存追加

```bash
cd frontend
npm i google-auth-library
```

### 3.3 IAP プロキシ用ユーティリティ

`frontend/lib/iapProxy.ts`:
```ts
import { GoogleAuth, IdTokenClient } from 'google-auth-library';

const IAP_AUDIENCE = process.env.IAP_AUDIENCE!;
const DEPLOY_QS_BASE_URL = process.env.DEPLOY_QS_BASE_URL!;

let clientPromise: Promise<IdTokenClient> | null = null;
function getClient() {
  if (!clientPromise) {
    const auth = new GoogleAuth();
    clientPromise = auth.getIdTokenClient(IAP_AUDIENCE);
  }
  return clientPromise;
}

const HOP_BY_HOP = new Set([
  'connection', 'keep-alive', 'transfer-encoding',
  'content-encoding', 'content-length', 'host',
]);

export async function forward(req: Request, subpath: string): Promise<Response> {
  const client = await getClient();
  const headers = await client.getRequestHeaders();         // Authorization が入る
  const url = new URL(`${DEPLOY_QS_BASE_URL.replace(/\/$/, '')}/${subpath}`);
  new URL(req.url).searchParams.forEach((v, k) => url.searchParams.append(k, v));

  const init: RequestInit = {
    method: req.method,
    headers: {
      ...Object.fromEntries(
        [...req.headers.entries()].filter(([k]) => !HOP_BY_HOP.has(k.toLowerCase()))
      ),
      ...headers,
    },
  };
  if (!['GET', 'HEAD'].includes(req.method)) {
    init.body = await req.arrayBuffer();
    (init as any).duplex = 'half';
  }

  const upstream = await fetch(url, init);
  const respHeaders = new Headers();
  upstream.headers.forEach((v, k) => {
    if (!HOP_BY_HOP.has(k.toLowerCase())) respHeaders.set(k, v);
  });
  return new Response(upstream.body, { status: upstream.status, headers: respHeaders });
}
```

### 3.4 Route Handler（catch-all）

`frontend/app/api/qs/[...path]/route.ts`:
```ts
import { forward } from '@/lib/iapProxy';

// Next.js 15: params は Promise
type Ctx = { params: Promise<{ path: string[] }> };

async function handler(req: Request, ctx: Ctx) {
  const { path } = await ctx.params;
  return forward(req, path.join('/'));
}

export const dynamic = 'force-dynamic';  // キャッシュ無効
export const runtime = 'nodejs';         // google-auth-library は Node ランタイム必須

export { handler as GET, handler as POST, handler as PUT, handler as DELETE, handler as PATCH };
```

### 3.5 frontend のフェッチコード

`frontend/lib/qs.ts`:
```ts
export async function qsFetch(path: string, init?: RequestInit) {
  // 同一オリジン → 相対パスでOK
  const res = await fetch(`/api/qs/${path.replace(/^\//, '')}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`upstream ${res.status}`);
  return res.json();
}
```

---

## 4. Firebase App Hosting のセットアップ

### 4.1 既存 Firebase Hosting 設定との関係
- `firebase.json` の `hosting`（静的書き出し前提）は **App Hosting に置き換える**
- 既存 `firebase.json` は残しても良いが、App Hosting は別管理（`apphosting.yaml`）

### 4.2 バックエンド作成

```bash
cd /Users/hiruta/work/flask-cluade-api
firebase login
firebase use --add        # Firebase プロジェクトを紐付け
firebase init apphosting  # ウィザード
#   ? Backend region: asia-northeast1
#   ? Root directory: frontend
#   ? GitHub repo: (連携する場合)
```

`apphosting.yaml`（自動生成 → 環境変数を追記）:
```yaml
runConfig:
  minInstances: 0
  maxInstances: 10
  concurrency: 80
  cpu: 1
  memoryMiB: 512
  # 任意でカスタム SA を指定
  # serviceAccount: my-sa@<project>.iam.gserviceaccount.com

env:
  - variable: IAP_AUDIENCE
    value: "<IAP の OAuth Client ID>"
    availability: [RUNTIME]

  - variable: DEPLOY_QS_BASE_URL
    value: "https://deploy-qs-dev-xxxxxxxx.<region>.run.app"
    availability: [RUNTIME]

  # Secret Manager を使う場合（推奨）
  # - variable: SOME_SECRET
  #   secret: projects/<project>/secrets/SOME_SECRET/versions/latest
  #   availability: [RUNTIME]
```

`package.json` のスクリプトは App Hosting がそのまま使う:
```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  }
}
```
> App Hosting は内部で `npm run build` → `npm run start` を実行します。**`next start` が動く形**（つまり static export ではない）にしておけば OK。

### 4.3 デプロイ

```bash
# Git 連携している場合は push で自動デプロイ
git push origin main

# CLI から手動デプロイ
firebase deploy --only apphosting
```

デプロイ後、`https://<backend-id>--<project>.<region>.hosted.app` のような URL が払い出されます。カスタムドメインも Console から接続可能。

---

## 5. ローカル開発

### 5.1 ADC の準備（IAP 越し呼び出しに必要）

ローカル `npm run dev` で動かす Next.js から IAP に通すには、ローカル ADC が App Hosting ランタイム SA を **impersonate** する必要があります。

```bash
SA="firebase-app-hosting-compute@${PROJECT_ID}.iam.gserviceaccount.com"

# 1) 自分が SA を impersonate できる権限（管理者一度だけ）
gcloud iam service-accounts add-iam-policy-binding $SA \
  --member="user:hiruta@totalsolution.biz" \
  --role="roles/iam.serviceAccountTokenCreator"

# 2) ADC を SA impersonation で設定
gcloud auth application-default login --impersonate-service-account=$SA
```

> 注: `gcloud auth application-default login` 単独だとユーザーアカウント ADC になり、ユーザーは ID トークン署名権限を持たないため `getIdTokenClient` が失敗します。**必ず impersonation 付き**で。

### 5.2 環境変数

`frontend/.env.local`:
```
IAP_AUDIENCE=<IAP の OAuth Client ID>
DEPLOY_QS_BASE_URL=https://deploy-qs-dev-xxxxxxxx.<region>.run.app
```

### 5.3 起動

```bash
cd frontend
npm run dev
# http://localhost:3000 でブラウザを開く
# 画面操作で /api/qs/... が叩かれ、Next.js サーバが IAP 越しに deploy-qs-dev へ
```

### 5.4 デバッグ
```bash
# ID トークンが取得できるか単体確認
node -e '
  const { GoogleAuth } = require("google-auth-library");
  (async () => {
    const auth = new GoogleAuth();
    const client = await auth.getIdTokenClient(process.env.IAP_AUDIENCE);
    const h = await client.getRequestHeaders();
    console.log(h.Authorization?.slice(0, 50), "...");
  })();
' 
```

---

## 6. 静的書き出しから SSR への移行で気を付けること

| 項目 | 影響 | 対応 |
| --- | --- | --- |
| `next/image` の `unoptimized` 設定 | export 前提だった場合は外せる | `next.config.ts` で `images.unoptimized` を削除可能 |
| `generateStaticParams` を使ったページ | SSR でも動くが、必要なら ISR/SSG に分岐 | `export const dynamic = 'force-static'` などで明示 |
| `<Link>` / クライアントナビゲーション | 影響なし | そのまま |
| ローカル開発時の `firebase serve` | 不要に | `npm run dev` に統一 |
| `firebase deploy`（Hosting） | App Hosting に置き換え | `firebase.json` の hosting 設定を削除 or 残しつつ別運用 |
| `out/` ディレクトリ | 不要に | `.gitignore` から削除しても良い |

既存ページ（`frontend/app/`）が React Server Components / Client Components の通常の Next.js 15 構成なら、コード変更は基本不要です。

---

## 7. セキュリティ・運用メモ

- **同一オリジン化により CORS が不要**。CSRF を別途考慮する（Next.js Server Actions は組み込みで CSRF 対策あり / 自前 Route Handler は同一 Origin チェックを `Origin` ヘッダで実施推奨）
- **ID トークンキャッシュ**: `google-auth-library` は `IdTokenClient` 内で自動キャッシュ・自動リフレッシュ
- **`force-dynamic`** にしておかないと Next.js のキャッシュに API レスポンスが乗ってしまうリスクがある
- **Secret Manager 連携**: `apphosting.yaml` の `secret:` 構文で App Hosting バックエンド経由で SA に自動付与（`roles/secretmanager.secretAccessor` の付与は CLI が案内）
- **観測性**: App Hosting バックエンドは Cloud Run なので、Cloud Run のメトリクス・ログがそのまま使える。`IAP` のアクセスログは負荷分散コンソール側

---

## 8. ロールバック / 段階移行

万一の保険として:
1. `firebase.json` の Hosting 設定はまず残しておく（既存の静的サイトはそのまま生存）
2. App Hosting バックエンドを別ドメイン or プレビューチャネルでデプロイ
3. 動作確認後、本ドメインを App Hosting に切替（Hosting → App Hosting への DNS 移行 or 公開設定変更）

---

## 9. チェックリスト

- [ ] IAP の OAuth Client ID を取得して `IAP_AUDIENCE` に設定
- [ ] App Hosting ランタイム SA に `roles/iap.httpsResourceAccessor` を付与
- [ ] IAP のアクセスメンバーに同 SA を追加
- [ ] `next.config.ts` から `output: 'export'` を削除
- [ ] `google-auth-library` を追加
- [ ] `lib/iapProxy.ts` と `app/api/qs/[...path]/route.ts` を実装
- [ ] frontend の fetch を `/api/qs/...` 相対パスに統一
- [ ] `apphosting.yaml` に環境変数を定義
- [ ] ローカルで `gcloud auth application-default login --impersonate-service-account=...`
- [ ] `npm run dev` で `/api/qs/...` の疎通確認
- [ ] `firebase deploy --only apphosting` で本番疎通確認
