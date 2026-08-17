# Cloud Run デプロイ前のローカル動作確認手順（flask-cloud-api-v2）

`flask-cloud-api-v2` は **Cloud Run にデプロイする Flask アプリ**です。デプロイ前のローカル検証手段は大きく分けて 3 通りあり、**用途に応じて使い分け**ます。

| 方法 | コマンド | 速度 | 本番再現度 | 用途 |
| --- | --- | --- | --- | --- |
| ① uv で直接起動 | `uv run flask --app src.app run` | ◎ 最速 | △ | 通常の開発・デバッグ |
| ② gunicorn で起動 | `uv run gunicorn -b 0.0.0.0:8000 src.app:app` | ○ | ○ | 本番と同じ WSGI 挙動の確認 |
| ③ Docker でビルド・起動 | `docker run ... <image>` | △ | ◎ | Cloud Run 直前の最終確認 |

> **推奨フロー**：開発中は ①、機能完成時に ②、Cloud Run へ `gcloud run deploy` する直前に ③。

---

## 1. 共通の前提セットアップ

### 1.1 依存ツール

```bash
# uv（Python 依存管理）
brew install uv

# Google Cloud SDK
brew install --cask google-cloud-sdk
```

### 1.2 Google Cloud 認証（ADC）

`cloud3_vertexai.py` が **Vertex AI の Claude (`ChatAnthropicVertex`)** を呼ぶため、ローカルから Google Cloud API を叩く ADC が必要です。

```bash
# Vertex AI 有効化 & 課金プロジェクト設定
gcloud auth login
gcloud config set project <YOUR_PROJECT_ID>
gcloud services enable aiplatform.googleapis.com

# ADC（ユーザー資格情報で OK。SA impersonation は不要）
gcloud auth application-default login
```

> **注**: IAP 経由の `iap-cloud-run-ssr-app-hosting.md` で出てきた `--impersonate-service-account=...` は **不要**。あれは「ID トークン発行」用で、Vertex AI 呼び出しは「アクセストークン」なのでユーザー ADC で動きます。

### 1.3 環境変数

`flask-cloud-api-v2/.env` を作成（uv は `.env` を自動読み込みしないので、後述する起動方法で明示的にロード）:

```bash
# Vertex AI 用
GOOGLE_CLOUD_PROJECT=<YOUR_PROJECT_ID>
GOOGLE_CLOUD_LOCATION=global

# Flask 用（任意）
FLASK_ENV=development
FLASK_DEBUG=1
PORT=8000
```

> `cloud3_vertexai.py` の `LOCATION = "global"` がハードコードされているため、Vertex AI のグローバルエンドポイントが有効なプロジェクトであることを確認してください。

### 1.4 依存インストール

```bash
cd flask-cloud-api-v2
uv sync           # .venv を作って依存を解決
```

---

## 2. ① uv で直接起動（最速）

開発中はこれが一番速いです。Flask の開発サーバはオートリロード対応。

```bash
cd flask-cloud-api-v2

# .env をシェルに読み込む（fish の場合）
set -a; source .env; set +a   # bash/zsh の場合
# fish の場合は ↓
# for line in (cat .env | grep -v '^#'); set -x (echo $line | cut -d= -f1) (echo $line | cut -d= -f2-); end

uv run flask --app src.app run --host 0.0.0.0 --port 8000 --debug
```

### 動作確認

```bash
# ヘルスチェック
curl http://localhost:8000/
# => {"message":"Hello world."}

# チャット（非ストリーミング）
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":{"text":"AWS S3とは"}}'

# チャット（SSE ストリーミング）
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":{"text":"こんにちは"}}'
```

### よくあるエラー

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| `google.auth.exceptions.DefaultCredentialsError` | ADC 未設定 | `gcloud auth application-default login` |
| `403 PERMISSION_DENIED ... aiplatform` | Vertex AI 未有効化 / 権限不足 | `gcloud services enable aiplatform.googleapis.com` + IAM で `roles/aiplatform.user` |
| `Quota exceeded` | global エンドポイントの初期クォータ | リージョン版に切り替えるか引き上げ申請 |
| `mcp ... connection refused` | AWS Knowledge MCP 疎通不可 | コードは fallback して LLM 単独で応答するため通常は無視可。社内 Proxy 環境なら `HTTPS_PROXY` 設定 |

---

## 3. ② gunicorn で起動（本番 WSGI を再現）

Cloud Run 本番は Dockerfile に書かれた **gunicorn (worker=2, timeout=120)** で動きます。
WSGI 起動時固有の挙動（並列処理、SSE の bufferring など）を確認したい場合はこちら。

```bash
cd flask-cloud-api-v2

uv run gunicorn -w 2 -b 0.0.0.0:8000 src.app:app --timeout 120
```

### SSE のバッファリング確認ポイント

`gunicorn` 単体だと SSE のチャンクがバッファされない場合があります。本番の Cloud Run でも `X-Accel-Buffering: no` を返しているので問題ないですが、**`curl -N` でリアルタイムに `data:` が降ってくるか**を必ず確認してください。

```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":{"text":"長めの応答を生成して"}}'
```

---

## 4. ③ Docker でビルド・起動（本番に最も近い）

Cloud Run は実質「コンテナを動かすだけ」なので、**Dockerfile でビルドしたイメージがローカルで動けば、Cloud Run でも 99% 動きます**。

### 4.1 ビルド

```bash
cd flask-cloud-api-v2
docker build -t flask-cloud-api-v2:local .
```

### 4.2 起動（ADC をコンテナにマウント）

ローカルの ADC を読み取り専用でコンテナにマウントするのがポイント:

```bash
docker run --rm -p 8000:8000 \
  -e PORT=8000 \
  -e GOOGLE_CLOUD_PROJECT=<YOUR_PROJECT_ID> \
  -e GOOGLE_APPLICATION_CREDENTIALS=/gcp/adc.json \
  -v "$HOME/.config/gcloud/application_default_credentials.json:/gcp/adc.json:ro" \
  flask-cloud-api-v2:local
```

> **重要**: Cloud Run 本番ではコンテナはメタデータサーバから自動取得するため、`GOOGLE_APPLICATION_CREDENTIALS` の指定は **不要**。ローカル Docker でだけ必要なテクニックです。

### 4.3 Cloud Run の制約をローカルで模倣

Cloud Run 固有の制約に近づけたい場合は次のオプションを追加:

```bash
docker run --rm -p 8000:8000 \
  --memory=1g --cpus=1 \                    # run-dev.yaml の resources.limits と一致
  --read-only --tmpfs /tmp \                # Cloud Run はルートファイルシステム書き込み不可
  -e PORT=8000 \
  -e GOOGLE_CLOUD_PROJECT=<YOUR_PROJECT_ID> \
  -e GOOGLE_APPLICATION_CREDENTIALS=/gcp/adc.json \
  -v "$HOME/.config/gcloud/application_default_credentials.json:/gcp/adc.json:ro" \
  flask-cloud-api-v2:local
```

これで「Cloud Run でだけ落ちる」系のバグ（一時ファイル書き込み、メモリオーバーなど）を事前に検出できます。

### 4.4 SIGTERM ハンドリングの確認（任意）

Cloud Run はスケールイン時に SIGTERM を送ります。コンテナを `docker stop <container>` してすぐ落ちるかを確認:

```bash
# 別ターミナルで
docker stop -t 10 $(docker ps -q --filter ancestor=flask-cloud-api-v2:local)
```

gunicorn は SIGTERM で graceful shutdown するため、10 秒以内に落ちれば OK。

---

## 5. frontend と組み合わせた疎通確認

`frontend`（Next.js）から `flask-cloud-api-v2` を呼ぶエンドツーエンド検証。

### 5.1 frontend の API ベース URL を切り替え

`frontend/.env.local`:
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

> Flask 側は `CORS(app)` で全許可しているのでローカルは CORS スルーで OK。

### 5.2 同時起動

```bash
# ターミナル 1: Flask
cd flask-cloud-api-v2
uv run flask --app src.app run --port 8000 --debug

# ターミナル 2: Next.js
cd frontend
npm run dev
```

`http://localhost:3000` を開いてチャットを送信 → `/api/chat/stream` に POST が飛び、SSE で逐次表示されれば成功。

---

## 6. デプロイ直前のチェックリスト

| 項目 | 確認方法 |
| --- | --- |
| `uv run flask` で起動できる | ① の手順 |
| `gunicorn` で起動できる | ② の手順 |
| Docker イメージがローカルで起動できる | ③ の手順 |
| `/` `/api/chat` `/api/chat/stream` `/api/chat/reset` の 4 endpoint が応答 | curl で叩く |
| `--read-only --tmpfs /tmp` でも落ちない | ③ のオプション付き |
| frontend から相対パス or `localhost:8000` で疎通 | 5 章 |
| `GOOGLE_CLOUD_PROJECT` を Cloud Run 側にも設定する準備ができている | `gcloud run deploy --set-env-vars=...` で渡す or `run-dev.yaml` を更新 |
| Cloud Run サービスアカウントに `roles/aiplatform.user` を付与 | `gcloud projects add-iam-policy-binding` |

---

## 7. トラブルシュート早見表

| ローカルで起きる症状 | 本番でも起きる？ | 切り分け |
| --- | --- | --- |
| `DefaultCredentialsError` | **本番では起きない**（メタデータサーバ） | ローカルだけ ADC を設定 |
| Vertex AI の `403` | 本番でも起きる可能性大 | プロジェクトの API 有効化 / SA 権限 |
| SSE のチャンクが纏まる | **本番（Cloud Run + HTTPS LB）でも起きうる** | `X-Accel-Buffering: no` ヘッダ確認、gunicorn worker class を `gthread` に |
| MCP（AWS Knowledge）接続失敗 | ネットワーク要件次第 | コードは fallback あり。Cloud Run の egress 設定確認 |
| 起動が遅い（コールドスタート） | 本番でも起きる | gunicorn の `--preload` 検討、`min-instances=1` |
| `/tmp` 以外に書き込もうとして失敗 | **本番でも起きる**（root FS 読み取り専用） | ③ の `--read-only` で事前検出 |

---

## 8. 参考: 本リポジトリの構成

```
flask-cloud-api-v2/
├── Dockerfile              # gunicorn -w 2 -b 0.0.0.0:8000 src.app:app
├── pyproject.toml          # uv 管理、Python >=3.12.5
├── src/app.py              # Flask エントリポイント
└── modules/
    ├── cloud3_vertexai.py  # Vertex AI Claude（要 ADC）
    ├── aws_knowledge.py    # AWS Knowledge MCP（公開エンドポイント / 認証不要）
    └── session_store.py    # インメモリセッション（複数インスタンス時は要差し替え）
```

`run-dev.yaml` には Cloud Run のサービス定義（`deploy-qs-dev` / 1 CPU / 1 GiB）があるので、③ の Docker 起動時の `--memory=1g --cpus=1` と揃えておくと本番再現度が上がります。
