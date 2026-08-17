# 会話履歴の保持機能

## 目的

これまで `/api/chat` / `/api/chat/stream` は 1 メッセージのみを LLM に渡しており、
過去の会話コンテキストを保持していなかった。次のプロンプトに前のやり取りを引き継げるよう、
バックエンド側でセッション単位の履歴管理を追加した。

## 全体像

```
┌──────────────┐   POST /api/chat/stream                ┌──────────────────┐
│  Frontend    │ ──{ message, session_id }────────────▶ │   Flask (app.py) │
│ (Next.js)    │                                        │                  │
│              │ ◀──SSE { session_id, chunk, text }──── │  session_store   │
└──────────────┘                                        │  cloud3_vertexai │
                                                        └──────────────────┘
```

- 履歴管理は **バックエンド** が `session_id` をキーに保持する方式
- `session_id` はサーバ側で UUID を発行し、レスポンスでクライアントに返す
- クライアント (Next.js) は `localStorage` に `session_id` を保持し、次回以降のリクエストに付与
- 直近 20 メッセージのみ保持し、超えた分は古いものから捨てる
- 1 時間アクセスのないセッションは TTL で自動破棄

## 変更ファイル一覧

| パス | 種別 | 概要 |
| --- | --- | --- |
| `flask-cloud-api-v2/modules/session_store.py` | 新規 | スレッドセーフなインメモリセッションストア |
| `flask-cloud-api-v2/modules/cloud3_vertexai.py` | 更新 | `history` を受け取り `HumanMessage` / `AIMessage` を組み立てて LLM に渡す |
| `flask-cloud-api-v2/src/app.py` | 更新 | `session_id` の受け渡し / `/api/chat/reset` 追加 |
| `frontend/types/chat.ts` | 更新 | `SSEData.session_id` を追加 |
| `frontend/lib/storage.ts` | 更新 | `session_id` を `localStorage` に保持するヘルパー追加 |
| `frontend/hooks/useChat.ts` | 更新 | リクエストに `session_id` を付与し、SSE から受け取った id を保存。`clearChat` で `/api/chat/reset` を呼ぶ |

## API 仕様

### POST `/api/chat`

リクエスト
```json
{
  "message": { "text": "今日は何曜日?" },
  "session_id": "<optional UUID>"
}
```

レスポンス
```json
{
  "text": "...",
  "session_id": "<UUID>"
}
```

### POST `/api/chat/stream` (SSE)

リクエストは上と同じ。レスポンスは SSE で以下の順に流れる。

1. `data: {"session_id": "<UUID>"}` （ストリーム開始直後に 1 度）
2. `data: {"chunk": "...", "text": "..."}` （部分テキスト）
3. `data: {"done": true, "text": "...", "session_id": "<UUID>"}` （完了通知）
4. エラー時は `data: {"error": "...", "session_id": "<UUID>"}`

### POST `/api/chat/reset`

```json
{ "session_id": "<UUID>" }
```

該当セッションの履歴を破棄する。常に `{"ok": true}` を返す。

## サーバ側の保持仕様

- 実装: `modules/session_store.py` の `SessionStore`
- 上限: 直近 20 メッセージ (`MAX_MESSAGES`)
- TTL: 最終アクセスから 1 時間 (`TTL_SECONDS`)
- 競合制御: `threading.Lock` で保護
- スコープ: **単一プロセス**

> 注意: Cloud Run などで複数インスタンスにスケールさせる場合、
> プロセスごとに状態が分かれてしまうため Firestore / Redis 等に差し替える必要がある。
> 現状の構成は単一インスタンス前提のシンプル実装。

## クライアント側の保持仕様

- `localStorage` キー
  - `chat_messages`: 画面表示用のメッセージ配列（既存）
  - `chat_session_id`: バックエンドから発行された `session_id` （新規）
- `useChat()` の初期化時に両方を復元する
- 送信時のリクエストボディに `session_id` を含める
- SSE から `session_id` を受け取ったら `ref` と `localStorage` を更新
- `clearChat()` は
  1. 画面とローカル履歴をクリア
  2. サーバへ `/api/chat/reset` を送信して履歴を破棄

## 動作確認手順

1. バックエンド起動
   ```bash
   cd flask-cloud-api-v2
   uv run gunicorn -k gthread -w 1 -b 0.0.0.0:8000 src.app:app
   ```
2. フロントエンド起動
   ```bash
   cd frontend
   npm run dev
   ```
3. ブラウザでチャット画面を開き、
   - 「私の名前はタロウです」と送信
   - 続けて「私の名前は何でしたか?」と送信し、`タロウ` が返ることを確認
4. 「クリア」ボタンで履歴をリセットし、再度「私の名前は何でしたか?」と送ると分からない旨が返ることを確認

## 今後の改善候補

- Cloud Run マルチインスタンス対応のため Firestore / Redis にバックエンドストアを差し替え
- メッセージ削除ロジックをトークン数ベースに改善 (`MAX_MESSAGES` ではなく合計トークン上限)
- 長期会話のサマリ化 (古いメッセージを要約して残す)
- セッションごとのシステムプロンプト設定
