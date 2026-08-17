# IAP 保護 Cloud Run (`deploy-qs-dev`) への frontend からのアクセス設計

## 1. 結論サマリ

| 項目 | 内容 |
| --- | --- |
| 推奨方式 | **BFF パターン**（フロント → Flask BFF → IAP 越しに `deploy-qs-dev`） |
| BFF 実体 | 既存の `flask-cloud-api-v2`（ローカルは `localhost:8080`、本番は Cloud Run） |
| 認証トークン | サービスアカウントの **OIDC ID トークン**（audience = IAP の OAuth Client ID） |
| frontend 側 | `localhost:3000` (Next.js dev) からは BFF だけを叩く。IAP の存在を意識しない |

```
[Browser localhost:3000]
        │  fetch('/api/qs/...') ※ BFF のエンドポイント
        ▼
[Flask BFF localhost:8080 / Cloud Run]
        │  Authorization: Bearer <ID_TOKEN>
        │  audience = IAP OAuth Client ID
        ▼
[IAP] ─ 検証 OK ─▶ [Cloud Run: deploy-qs-dev]
```

なぜこの形か:
- Next.js は `output: 'export'` の静的書き出しで Firebase Hosting 配信。**API Routes が使えない**ため、フロント側にサーバを置けない
- フロントから直接 IAP を叩く構成は CORS / トークン管理 / Client ID 露出の点で運用が厳しい
- 既に Flask Cloud Run が存在するので、これに `/api/qs/*` のプロキシエンドポイントを足すだけで完結

---

## 2. 前提情報の収集（最初に必ず確認）

### 2.1 IAP の OAuth Client ID を取得
Cloud Run の IAP を有効化すると、内部で OAuth 2.0 Client ID が払い出されています。これが ID トークンの **audience** になります。

```bash
# プロジェクト ID は適宜
PROJECT_ID="<your-project-id>"

# IAP の OAuth ブランド/クライアントを確認
gcloud iap oauth-brands list --project=$PROJECT_ID
gcloud iap oauth-clients list <BRAND_NAME> --project=$PROJECT_ID
```

Console から確認する場合:
- Console → セキュリティ → Identity-Aware Proxy → 対象 Cloud Run の行 → 「OAuth 構成」または APIとサービス → 認証情報 で `IAP-<resource>-<service-name>` のような Client ID

得られた値を以下に保存:
```
IAP_AUDIENCE = "<NUMBER>-<HASH>.apps.googleusercontent.com"
CLOUD_RUN_URL = "https://deploy-qs-dev-xxxxxxxx.<region>.run.app"
```

### 2.2 BFF 用サービスアカウントの準備

```bash
SA_NAME="flask-bff-iap-invoker"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create $SA_NAME \
  --display-name="Flask BFF (calls IAP-protected Cloud Run)" \
  --project=$PROJECT_ID

# IAP 越しのリソースアクセス権
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iap.httpsResourceAccessor"

# 念のため Cloud Run Invoker も付与（IAP が前段でも、Cloud Run 側 IAM の併用構成の場合に必要）
gcloud run services add-iam-policy-binding deploy-qs-dev \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker" \
  --region=<region> --project=$PROJECT_ID
```

---

## 3. ローカル開発の認証セットアップ

ローカルの Flask BFF からサービスアカウントとして ID トークンを発行するには **Service Account Impersonation** を使うのが安全（鍵ファイルを使わない）。

```bash
# 1. 自分のユーザーがそのサービスアカウントを「成りすませる」権限を付与（管理者が一度実施）
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --member="user:hiruta@totalsolution.biz" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project=$PROJECT_ID

# 2. ADC を impersonation 付きで設定（開発者の端末で実行）
gcloud auth application-default login --impersonate-service-account=$SA_EMAIL
```

これで `google.auth.default()` から取得される credentials が SA のものとして振る舞います。鍵 JSON のローカル保管は不要。

---

## 4. Flask BFF 側の実装

`flask-cloud-api-v2` に以下を追加します。

### 4.1 依存追加 (`pyproject.toml`)

```toml
[project]
dependencies = [
  # ... 既存 ...
  "google-auth>=2.35.0",
  "requests>=2.32.0",
]
```

```bash
uv sync
```

### 4.2 IAP 呼び出しユーティリティ

`flask-cloud-api-v2/modules/iap_client.py` を新規作成:

```python
"""IAP 保護 Cloud Run を呼び出すための薄いラッパ。

ID トークンは audience(=IAP OAuth Client ID) ごとにキャッシュされ、
google-auth が内部で 5 分前リフレッシュを行う。
"""
import os
from functools import lru_cache

import google.auth
import google.auth.transport.requests
from google.oauth2 import id_token

_AUDIENCE = os.environ["IAP_AUDIENCE"]            # 例: 12345-xxxx.apps.googleusercontent.com
_TARGET_BASE = os.environ["DEPLOY_QS_BASE_URL"]   # 例: https://deploy-qs-dev-xxx.run.app


@lru_cache(maxsize=1)
def _request():
    return google.auth.transport.requests.Request()


def _fetch_id_token() -> str:
    """ADC のサービスアカウントで audience 付き ID トークンを取得する。"""
    # Metadata Server (Cloud Run 上) でも、impersonation 済み ADC (ローカル) でも動く。
    return id_token.fetch_id_token(_request(), _AUDIENCE)


def call(method: str, path: str, **kwargs):
    """IAP 越しに deploy-qs-dev を呼ぶ。`requests` と同じシグネチャ。"""
    import requests

    url = f"{_TARGET_BASE.rstrip('/')}/{path.lstrip('/')}"
    headers = kwargs.pop("headers", {}) or {}
    headers["Authorization"] = f"Bearer {_fetch_id_token()}"
    headers.setdefault("Content-Type", "application/json")
    return requests.request(method, url, headers=headers, timeout=30, **kwargs)
```

### 4.3 プロキシエンドポイント

`flask-cloud-api-v2/src/app.py` に追加:

```python
from flask import Blueprint, Response, request
from modules import iap_client

qs_bp = Blueprint("qs", __name__, url_prefix="/api/qs")

@qs_bp.route("/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def proxy(subpath: str):
    upstream = iap_client.call(
        request.method,
        subpath,
        params=request.args,
        data=request.get_data() or None,
    )
    # 一部のヘッダは flask が握るので転送しない
    excluded = {"content-encoding", "content-length", "transfer-encoding", "connection"}
    headers = [(k, v) for k, v in upstream.headers.items() if k.lower() not in excluded]
    return Response(upstream.content, status=upstream.status_code, headers=headers)

app.register_blueprint(qs_bp)
```

### 4.4 CORS（ローカルの Next.js から叩くため）

`flask-cloud-api-v2` に CORS 設定がまだ無ければ追加:

```python
from flask_cors import CORS

CORS(
    app,
    resources={r"/api/*": {"origins": ["http://localhost:3000"]}},
    supports_credentials=False,  # ID トークンは BFF が持つので不要
)
```

### 4.5 環境変数

ローカル `.env` 等:
```
IAP_AUDIENCE=12345-xxxx.apps.googleusercontent.com
DEPLOY_QS_BASE_URL=https://deploy-qs-dev-xxxxxxxx.<region>.run.app
```

---

## 5. frontend (Next.js) 側

特別な認証コードは不要。**BFF を `fetch` するだけ**。

`frontend/lib/qs.ts` を新規:
```ts
const BFF_BASE = process.env.NEXT_PUBLIC_BFF_BASE_URL ?? 'http://localhost:8080';

export async function qsFetch(path: string, init?: RequestInit) {
  const res = await fetch(`${BFF_BASE}/api/qs/${path.replace(/^\//, '')}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) throw new Error(`BFF error ${res.status}`);
  return res.json();
}
```

`frontend/.env.local`:
```
NEXT_PUBLIC_BFF_BASE_URL=http://localhost:8080
```

---

## 6. 動作確認

```bash
# 1) Flask BFF を起動
cd flask-cloud-api-v2
uv run flask --app src.app run --port 8080

# 2) ID トークンが取れているか単体確認
uv run python -c "
from modules.iap_client import _fetch_id_token
print(_fetch_id_token()[:40], '...')
"

# 3) BFF 経由で IAP 越しに叩く
curl -s http://localhost:8080/api/qs/<実際のエンドポイント> | jq

# 4) Next.js 起動
cd ../frontend
npm run dev
```

期待結果:
- BFF のレスポンスが 200 で返る
- IAP 側のアクセスログに **`flask-bff-iap-invoker@...` がプリンシパル** として記録される

---

## 7. 本番運用時の差分

| 項目 | ローカル | 本番（Cloud Run） |
| --- | --- | --- |
| ADC | `gcloud auth ... --impersonate-service-account` | Cloud Run のランタイム SA（= `SA_EMAIL`）を使うので何もしない |
| Metadata Server | 無し → `id_token.fetch_id_token` は impersonated SA で署名 | 自動的に Metadata Server が ID トークン発行 |
| BFF URL | `http://localhost:8080` | Cloud Run の URL（Firebase Hosting からは `rewrites` で同一オリジン化推奨） |
| CORS | `http://localhost:3000` を許可 | Firebase Hosting のドメインを許可、または `rewrites` で不要化 |

Firebase Hosting の `rewrites` 例（API を同一オリジン化）:
```json
{
  "hosting": {
    "public": "out",
    "rewrites": [
      { "source": "/api/qs/**", "run": { "serviceId": "flask-cloud-api-v2", "region": "<region>" } }
    ]
  }
}
```
→ frontend は `/api/qs/...` を相対パスで叩くだけになり CORS 不要。

---

## 8. トラブルシューティング

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| BFF から 302 が返り `accounts.google.com/...` にリダイレクト | ID トークン未付与 or audience 不一致 | `IAP_AUDIENCE` を IAP の OAuth Client ID と一致させる |
| `403 You don't have access` | SA に `roles/iap.httpsResourceAccessor` 未付与、または IAP のアクセスリストから外れている | Console → IAP → 対象 → 「メンバーを追加」で SA を追加 |
| `Could not automatically determine credentials` | ADC 未設定 | `gcloud auth application-default login --impersonate-service-account=$SA_EMAIL` |
| ローカルから `id_token.fetch_id_token` が `IDTokenCredentials` エラー | impersonation していない素の user ADC は ID トークンを発行できない | 上記 impersonation 付き ADC を使う |
| CORS エラー（preflight 失敗） | flask-cors の `origins` に `http://localhost:3000` がない | 4.4 を確認 |

---

## 9. 代替案メモ（採用しなかった理由）

- **フロントから直接 OIDC ID トークンを取得して送信**
  - IAP の OAuth Client ID をフロントに埋め込む必要があり、認可スコープ管理が散らかる
  - `output: 'export'` の SPA 配信では認証フローの後処理が煩雑
- **ブラウザリダイレクト方式（IAP の Cookie 認証）**
  - SPA の XHR/fetch とは相性が悪い（IAP は限定的にしか CORS を返さない）
  - ページ遷移型なら成立するが、Next.js の SPA ナビゲーションで破綻しやすい
- **IAP を外して Cloud Run IAM + Firebase Auth に置換**
  - 設計としては綺麗だが、`deploy-qs-dev` 側の認可方針変更を伴うので影響範囲が大きい
