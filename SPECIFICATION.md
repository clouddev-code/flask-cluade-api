# Flask Claude API プロジェクト 仕様書

## プロジェクト概要

### 目的
複数のAIモデルプロバイダー（Google Vertex AI、AWS Bedrock）と統合された、ストリーミング対応のチャットAPIサービスを提供する。

### プロジェクト名
`flask-cloud-api`

### バージョン
1.0.0

---

## システムアーキテクチャ

### 全体構成

```
┌─────────────────┐      HTTP/SSE      ┌──────────────────┐
│   Next.js       │ ◄────────────────► │   Flask API      │
│   Frontend      │                    │   (Gunicorn)     │
└─────────────────┘                    └──────────────────┘
                                              │
                                              ├─► Google Vertex AI
                                              │   └─ Claude Sonnet 4.5
                                              │   └─ Gemini 2.5 Pro
                                              │
                                              ├─► AWS Bedrock
                                              │   └─ Claude Sonnet 4
                                              │
                                              └─► Sakura AI API
                                                  └─ GPT-OSS-120B
```

### デプロイメント環境

- **開発環境**: ローカルDocker、Google Cloud Run
- **本番環境**: AWS EKS (Kubernetes)
- **コンテナレジストリ**: AWS ECR (東京リージョン)
- **ロードバランサー**: AWS Application Load Balancer (ALB)

---

## 技術スタック

### バックエンド

| 技術 | バージョン | 用途 |
|-----|-----------|------|
| Python | 3.12.11 | 開発言語 |
| Flask | 3.1.0 | Webフレームワーク |
| Gunicorn | 23.0.0 | WSGIサーバー |
| LangChain | 0.3.20+ | LLMオーケストレーション |
| Pydantic | 2.11.3 | データバリデーション |
| uv | - | パッケージマネージャー |

### AIモデルプロバイダー

| プロバイダー | モデル | リージョン/設定 |
|------------|-------|---------------|
| Google Vertex AI | Claude Sonnet 4.5 | プロジェクトID: `infra-dev-392306` |
| Google Vertex AI | Gemini 2.5 Pro | ロケーション: `us-east5` |
| AWS Bedrock | Claude Sonnet 4 | リージョン: `us-west-2` |
| Sakura AI API | GPT-OSS-120B | - |

### フロントエンド

| 技術 | バージョン | 用途 |
|-----|-----------|------|
| Next.js | 15.3.0 | Reactフレームワーク |
| React | 19.0.0 | UIライブラリ |
| TypeScript | 5 | 型付き開発 |
| Tailwind CSS | 3.4.1 | スタイリング |

### インフラストラクチャ

- **コンテナ化**: Docker
- **オーケストレーション**: Kubernetes (AWS EKS)
- **サーバーレス**: Google Cloud Run
- **CI/CD**: Skaffold, Cloud Deploy
- **モニタリング**: Langfuse, LangSmith

---

## API仕様

### ベースURL

- **開発**: `http://localhost:8000`
- **本番**: EKS/ALB経由のURL

### エンドポイント一覧

#### 1. ヘルスチェック

```
GET /
```

**レスポンス例**:
```json
{
  "message": "Hello world."
}
```

#### 2. 通常チャット (非ストリーミング)

```
POST /api/chat
```

**リクエストボディ**:
```json
{
  "message": {
    "text": "ユーザーのメッセージ"
  }
}
```

**レスポンス**:
```json
{
  "text": "AIの応答テキスト"
}
```

**ステータスコード**:
- `200 OK`: 正常処理
- `400 Bad Request`: リクエストエラー
- `500 Internal Server Error`: サーバーエラー

**使用モジュール**: `cloud3_vertexai.chatcompletion()`

#### 3. ストリーミングチャット

```
POST /api/chat/stream
```

**リクエストボディ**:
```json
{
  "message": {
    "text": "ユーザーのメッセージ"
  }
}
```

**レスポンス形式**: Server-Sent Events (SSE)

**レスポンスヘッダー**:
```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
Connection: keep-alive
```

**SSEデータ形式**:
```
data: {"chunk": "テキストの断片", "text": "累積テキスト"}

data: {"chunk": "次の断片", "text": "累積テキスト"}

data: {"done": true, "text": "完全な応答テキスト"}
```

**エラー時**:
```
data: {"error": "エラーメッセージ"}
```

**使用モジュール**: `cloud3_vertexai.chatcompletion_stream()`

---

## データモデル

### Pydanticスキーマ (`schemas.py`)

#### ChatRequest
```python
class ChatRequest(BaseModel):
    text: str  # ユーザーのメッセージテキスト
```

#### ChatResponse
```python
class ChatResponse(BaseModel):
    message: str  # AIの応答メッセージ
```

### TypeScript型定義 (`frontend/types/chat.ts`)

#### Message
```typescript
interface Message {
  id: string;           // メッセージID (UUID)
  role: 'user' | 'assistant';  // 送信者
  content: string;      // メッセージ内容
  timestamp: number;    // タイムスタンプ (UNIX時間)
}
```

#### SSEData
```typescript
interface SSEData {
  chunk?: string;   // ストリーミング中のテキスト断片
  text?: string;    // 累積テキスト
  done?: boolean;   // ストリーミング完了フラグ
  error?: string;   // エラーメッセージ
}
```

---

## モジュール仕様

### 1. cloud3_vertexai.py

**目的**: Google Vertex AI上のClaude Sonnet 4.5との統合

**主要機能**:
- 通常チャット処理 (`chatcompletion`)
- ストリーミングチャット処理 (`chatcompletion_stream`)

**設定**:
- モデル: `claude-sonnet-4-5@20250514`
- プロジェクトID: `infra-dev-392306`
- リージョン: デフォルト
- Thinking Mode: 有効 (budget_tokens: 1600)
- 最大トークン数: 8000

**使用ライブラリ**: LangChain, ChatVertexAI

### 2. cloud3_bedrock.py

**目的**: AWS Bedrock上のClaude Sonnet 4との統合

**主要機能**:
- 通常チャット処理 (`chatcompletion`)
- ストリーミングチャット処理 (`chatcompletion_stream`)

**設定**:
- モデル: `us.anthropic.claude-sonnet-4-20250514-v1:0`
- リージョン: `us-west-2`
- Thinking Mode: 有効 (budget_tokens: 1024)
- 最大トークン数: 8000
- 観測性: Langfuse統合

**使用ライブラリ**: LangChain, ChatBedrock, Langfuse

### 3. gemini_vertexai.py

**目的**: Google Vertex AIのGemini 2.5 Pro統合

**主要機能**:
- 通常チャット処理 (`chatcompletion`)
- ストリーミングチャット処理 (`chatcompletion_stream`)

**設定**:
- モデル: `gemini-2.0-flash-exp`
- プロジェクトID: `infra-dev-392306`
- ロケーション: `us-east5`
- 最大トークン数: 8000
- 観測性: Langfuse統合

**使用ライブラリ**: LangChain, ChatVertexAI, Langfuse

### 4. gpt_vertexai.py

**目的**: Sakura AI APIのGPT-OSS-120Bモデル統合

**設定**:
- モデル: `gpt-oss-120b`
- 最大トークン数: 8000

**注意**: コードに未完成部分あり

---

## フロントエンド仕様

### 主要コンポーネント

#### Chat Component (`frontend/components/chat/`)
- チャットインターフェース
- メッセージ表示
- 入力フォーム

#### Hooks (`frontend/hooks/`)
- `useChat`: チャット機能の状態管理
- `useSSE`: Server-Sent Eventsハンドリング

### データ永続化

- **ストレージ**: LocalStorage
- **保存内容**: 会話履歴（Message配列）
- **キー**: `chat-history`

### ストリーミング処理

1. ユーザーがメッセージを送信
2. `/api/chat/stream`にPOSTリクエスト
3. SSE接続を確立
4. `data:`イベントを受信
5. チャンク毎にUIを更新
6. `done: true`で接続終了

---

## インフラストラクチャ仕様

### Docker設定 (`Dockerfile`)

```dockerfile
# ベースイメージ
FROM python:3.12.11-slim

# ワーキングディレクトリ
WORKDIR /app

# uvを使用した依存関係インストール
# マルチステージビルドで最適化

# 起動コマンド
gunicorn -w 2 -b 0.0.0.0:8000 --timeout 120 src.app:app
```

**ポート**: 8000
**ワーカー数**: 2
**タイムアウト**: 120秒

### Kubernetes設定 (`k8s/pod-deployment.yaml`)

**Namespace**: `test-app`

**Deployment**:
- 名前: `fastapi-app` (実際はFlask)
- レプリカ数: 2
- イメージ: `905860205176.dkr.ecr.ap-northeast-1.amazonaws.com/flasksample:tokyo`
- リソース:
  - CPU: 250m
  - メモリ: 500Mi

**Service**:
- タイプ: NodePort
- ポート: 8000

**Ingress**:
- クラス: `alb`
- スキーム: `internet-facing`
- ターゲットタイプ: `ip`
- ヘルスチェックパス: `/`
- ロードバランシングアルゴリズム: `weighted_random`

**ServiceAccount**: `akane-dev-irsa-service-account`

### Cloud Run設定 (`run-dev.yaml`)

- サービス名: `deploy-qs-dev`
- リージョン: `us-central1`
- CPU: 1000m
- メモリ: 1024Mi
- ポート: 8000
- 最小インスタンス数: 0
- タイムアウト: 3600秒

---

## 環境変数

### バックエンド必須環境変数

| 変数名 | 説明 | 例 |
|--------|------|-----|
| `GOOGLE_APPLICATION_CREDENTIALS` | Google Cloud認証情報のパス | `/path/to/service-account.json` |
| `AWS_ACCESS_KEY_ID` | AWS認証情報 (Bedrock用) | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | AWS認証情報 (Bedrock用) | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse公開キー | 現在ハードコード（要改善） |
| `LANGFUSE_SECRET_KEY` | Langfuseシークレットキー | 現在ハードコード（要改善） |
| `LANGFUSE_HOST` | LangfuseホストURL | `https://cloud.langfuse.com` |

### フロントエンド環境変数

| 変数名 | 説明 | デフォルト値 |
|--------|------|------------|
| `NEXT_PUBLIC_API_URL` | バックエンドAPIのURL | `http://localhost:8000` |

---

## セキュリティ考慮事項

### 現在の課題

1. **APIキーのハードコード**:
   - Langfuseの認証情報がソースコードに直接記述されています
   - **推奨**: 環境変数への移行

2. **プロジェクトIDの露出**:
   - Google CloudプロジェクトID `infra-dev-392306` がコードに記述
   - **推奨**: 環境変数または設定ファイルへの移行

3. **CORS設定**:
   - 現在は全オリジン許可 (`CORS(app)`)
   - **推奨**: 本番環境では特定オリジンのみ許可

### 推奨セキュリティ対策

- APIキー管理: AWS Secrets Manager / Google Secret Manager使用
- CORS制限: 本番環境では許可オリジンを明示的に設定
- レート制限: Flask-Limiterなどの導入
- 入力バリデーション: Pydanticスキーマの厳格化
- HTTPS強制: 本番環境ではHTTPS通信のみ許可

---

## デプロイメント手順

### ローカル開発環境

1. **依存関係インストール**:
   ```bash
   cd flask-cloud-api
   uv pip install -r requirements.txt
   ```

2. **アプリケーション起動**:
   ```bash
   python src/app.py
   # または
   gunicorn -w 2 -b 0.0.0.0:8000 src.app:app
   ```

3. **フロントエンド起動**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### Dockerデプロイ

1. **イメージビルド**:
   ```bash
   docker build -t flask-cloud-api .
   ```

2. **コンテナ起動**:
   ```bash
   docker run -p 8000:8000 flask-cloud-api
   ```

### Kubernetesデプロイ (AWS EKS)

1. **ECRにイメージプッシュ**:
   ```bash
   docker tag flask-cloud-api:latest 905860205176.dkr.ecr.ap-northeast-1.amazonaws.com/flasksample:tokyo
   docker push 905860205176.dkr.ecr.ap-northeast-1.amazonaws.com/flasksample:tokyo
   ```

2. **Kubernetesリソース適用**:
   ```bash
   kubectl apply -f k8s/pod-deployment.yaml
   ```

3. **デプロイメント確認**:
   ```bash
   kubectl get pods -n test-app
   kubectl get svc -n test-app
   kubectl get ingress -n test-app
   ```

### Cloud Runデプロイ

```bash
gcloud run services replace run-dev.yaml
```

---

## モニタリング・観測性

### Langfuse統合

- **対象モジュール**: `cloud3_bedrock.py`, `gemini_vertexai.py`
- **トレース情報**:
  - プロンプト内容
  - レスポンス内容
  - トークン使用量
  - レイテンシ

### ヘルスチェック

- **エンドポイント**: `GET /`
- **正常時レスポンス**: `{"message": "Hello world."}`
- **Kubernetes**: livenessProbe / readinessProbeで使用可能

---

## パフォーマンス仕様

### レスポンスタイム目標

- **通常チャット**: < 5秒
- **ストリーミング初回チャンク**: < 2秒

### スケーリング

- **Kubernetes**: HorizontalPodAutoscaler設定可能
- **Cloud Run**: 自動スケーリング対応

### リソース制限

- **Pod CPU**: 250m
- **Pod メモリ**: 500Mi
- **Cloud Run CPU**: 1000m
- **Cloud Run メモリ**: 1024Mi

---

## トラブルシューティング

### よくある問題

1. **認証エラー**:
   - Google Cloud / AWS認証情報を確認
   - サービスアカウントの権限確認

2. **ストリーミングが動作しない**:
   - プロキシ/ロードバランサーのバッファリング設定確認
   - `X-Accel-Buffering: no`ヘッダーの確認

3. **タイムアウトエラー**:
   - Gunicornタイムアウト設定 (デフォルト120秒)
   - Cloud Runタイムアウト設定 (デフォルト3600秒)

---

## 今後の改善事項

### 優先度: 高

1. **セキュリティ強化**:
   - APIキーの環境変数化
   - Secrets Manager使用

2. **コード品質**:
   - `gpt_vertexai.py`の未完成部分修正
   - 統一的なエラーハンドリング

3. **命名の整合性**:
   - Kubernetes設定の名前修正 (FastAPI → Flask)

### 優先度: 中

1. **機能拡張**:
   - 会話履歴のバックエンド保存
   - ユーザー認証機能
   - レート制限実装

2. **テスト**:
   - ユニットテスト追加
   - 統合テスト追加
   - E2Eテスト追加

3. **ドキュメント**:
   - API仕様書 (OpenAPI/Swagger)
   - アーキテクチャ図の追加

### 優先度: 低

1. **パフォーマンス最適化**:
   - キャッシング機能
   - CDN統合

2. **運用改善**:
   - ログ集約 (CloudWatch / Cloud Logging)
   - アラート設定

---

## 参考情報

### ドキュメント

- `README.md`: プロジェクト概要
- `STREAMLIT_README.md`: Streamlit版の説明

### 設定ファイル

- `pyproject.toml`: Python依存関係
- `package.json`: Node.js依存関係
- `skaffold.yaml`: Skaffold設定
- `cloudeploy.yaml`: Cloud Deploy設定

### ディレクトリ構成詳細

```
flask-cluade-api/
├── flask-cloud-api/          # バックエンド
│   ├── src/
│   │   └── app.py
│   ├── modules/
│   │   ├── cloud3_vertexai.py
│   │   ├── cloud3_bedrock.py
│   │   ├── gemini_vertexai.py
│   │   └── gpt_vertexai.py
│   ├── schemas.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                 # フロントエンド
│   ├── app/
│   ├── components/
│   ├── hooks/
│   ├── lib/
│   ├── types/
│   └── package.json
├── k8s/                      # Kubernetes設定
│   └── pod-deployment.yaml
├── network/                  # ネットワーク設定
└── main.py
```

---

## 変更履歴

| 日付 | バージョン | 変更内容 | 作成者 |
|------|-----------|---------|--------|
| 2025-11-08 | 1.0.0 | 初版作成 | Claude Code |

---

## ライセンス

プロジェクトのライセンスについては、リポジトリのLICENSEファイルを参照してください。

---

## お問い合わせ

プロジェクトに関する問い合わせは、GitHubリポジトリのIssuesセクションをご利用ください。
