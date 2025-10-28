# Streamlit Chat Frontend

`/api/chat/stream` エンドポイントを呼び出すStreamlitベースのチャットフロントエンドアプリケーションです。

## 機能

- リアルタイムストリーミング応答
- チャット履歴の保持
- Server-Sent Events (SSE) 対応
- エラーハンドリング
- レスポンシブなUI

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r streamlit_requirements.txt
```

### 2. Flask APIの起動

まず、バックエンドのFlask APIを起動してください：

```bash
# 開発環境の場合
python src/app.py

# または
flask run
```

デフォルトでは `http://localhost:5000` で起動します。

### 3. Streamlitアプリの起動

```bash
streamlit run streamlit_app.py
```

ブラウザが自動的に開き、アプリケーションが表示されます（通常は `http://localhost:8501`）。

## 使い方

1. アプリケーションが起動したら、サイドバーでAPI URLを確認/設定
   - デフォルト: `http://localhost:5000/api/chat/stream`

2. 画面下部の入力欄にメッセージを入力

3. Enterキーを押すか送信ボタンをクリック

4. AIがストリーミングでリアルタイムに応答を返します

5. 会話履歴をクリアする場合は、サイドバーの「会話履歴をクリア」ボタンをクリック

## API仕様

### リクエスト形式

```json
{
  "message": {
    "text": "ユーザーのメッセージ"
  }
}
```

### レスポンス形式（SSE）

ストリーミング中:
```
data: {"chunk": "テキストの断片", "text": "累積テキスト"}
```

完了時:
```
data: {"done": true, "text": "完全なレスポンステキスト"}
```

エラー時:
```
data: {"error": "エラーメッセージ"}
```

## トラブルシューティング

### APIに接続できない

- Flask APIが起動していることを確認
- API URLが正しいことを確認（サイドバーで設定可能）
- CORSの設定を確認（Flask側で適切に設定されている必要があります）

### ストリーミングが動作しない

- ブラウザがServer-Sent Eventsをサポートしているか確認
- プロキシやロードバランサーがストリーミングをブロックしていないか確認

### タイムアウトエラー

- リクエストタイムアウトは60秒に設定されています
- 必要に応じて `streamlit_app.py` の `timeout` パラメータを調整してください

## カスタマイズ

### API URLの変更

サイドバーで動的に変更可能ですが、デフォルト値を変更する場合は `streamlit_app.py` の以下の行を編集：

```python
API_URL = st.sidebar.text_input(
    "API URL",
    value="http://localhost:5000/api/chat/stream",  # ここを変更
    help="Flask APIのエンドポイントURL"
)
```

### タイムアウト時間の変更

```python
with requests.post(
    API_URL,
    json=payload,
    stream=True,
    headers={"Accept": "text/event-stream"},
    timeout=60  # この値を変更（秒単位）
) as response:
```

## ファイル構成

```
.
├── streamlit_app.py              # Streamlitアプリケーション本体
├── streamlit_requirements.txt    # Streamlit用の依存関係
├── STREAMLIT_README.md          # このファイル
└── src/
    └── app.py                    # Flask APIサーバー
```

## 技術スタック

- **Frontend**: Streamlit
- **Backend**: Flask (別プロセス)
- **通信**: Server-Sent Events (SSE)
- **HTTP Client**: requests

## ライセンス

プロジェクトのライセンスに従います。
