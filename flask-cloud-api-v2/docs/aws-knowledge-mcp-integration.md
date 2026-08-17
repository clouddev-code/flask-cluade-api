# AWS Knowledge MCP 統合

LLM の応答のみを返していた構成を改修し、AWS 関連の質問は AWS Knowledge MCP
(`https://knowledge-mcp.global.api.aws`) のツールを呼び出して
公式ドキュメントベースで回答するようにした。

## 採用方針

| 項目 | 内容 |
| --- | --- |
| 統合方式 | `langchain-mcp-adapters` で MCP ツールを取得し、`ChatAnthropicVertex` に `bind_tools` した手動 ReAct ループ |
| 公開ツール | `aws___search_documentation` / `aws___read_documentation` / `aws___recommend` |
| 対応エンドポイント | `/api/chat`(同期) と `/api/chat/stream`(SSE) の両方 |
| 認証 | AWS Knowledge MCP は認証不要 |
| フォールバック | MCP 接続失敗時はツールなしで通常応答 |

## 変更ファイル

### 追加

- `modules/aws_knowledge.py`
  - `MultiServerMCPClient` で MCP ツールを取得しプロセス内でキャッシュ
  - ツール名のサフィックスでフィルタ（`search_documentation` / `read_documentation` / `recommend`）

### 修正

- `pyproject.toml`
  - `langchain-mcp-adapters>=0.1.0` を追加
- `modules/cloud3_vertexai.py`
  - `bind_tools` + ReAct ループ実装（最大 5 反復）
  - System プロンプトで「AWS 関連は MCP ツールを優先」と指示
  - 同期エンドポイント: `asyncio.run` で async ループを駆動
  - ストリーミング: 新規イベントループを生成し非同期ジェネレータを逐次消費
  - 新しいストリーミング kind を追加: `tool_use` / `tool_result`
- `src/app.py`
  - `kind == "text"` のみを `full_text` に蓄積（ツールイベントが本文に混入しないよう修正）
- `frontend/types/chat.ts`
  - `SSEData.kind` に `'tool_use' | 'tool_result'` を追加

## 動作フロー

1. Flask が `/api/chat[/stream]` を受信
2. `chatcompletion(_stream)` 内で AWS Knowledge MCP からツール定義をロード（初回のみ）
3. `ChatAnthropicVertex` にツールを bind して Claude を呼び出し
4. Claude が AWS 関連質問と判断 → `tool_calls` を生成
5. ReAct ループで MCP ツールを実行し `ToolMessage` をフィードバック
6. `tool_calls` が無くなったら最終応答を返却（または stream 終了）

## ストリーミングイベント仕様

| kind | 内容 |
| --- | --- |
| `text` | 本文テキストの増分 |
| `thinking` | 思考プロセス（adaptive thinking） |
| `tool_use` | MCP ツール呼び出し開始（`{name, args}` の JSON） |
| `tool_result` | ツール実行結果のプレビュー（最大 500 文字） |

フロントエンドの `useChat` は `data.text` / `data.thinking` のみを参照しており、
ツールイベントが流れても本文や思考の表示は影響を受けない。

## フロントエンド: ツール呼び出しタイムライン

アシスタントメッセージ内に「ツール呼び出しを表示 (N 件)」の展開可能セクション
（thinking と同じスタイル、デフォルトは開いた状態）を表示する。

- `tool_use` 受信 → `message.toolCalls` に新規エントリ追加（スピナー表示）
- `tool_result` 受信 → 直近のエントリの `result` を埋める（チェック表示）

ツール名は `TOOL_LABELS` で日本語ラベルにマッピング:

| 生ツール名 | 表示名 |
| --- | --- |
| `aws___search_documentation` | AWSドキュメントを検索 |
| `aws___read_documentation` | AWSドキュメントを読み取り |
| `aws___recommend` | 関連AWSドキュメントを推薦 |

各エントリは以下を表示:
- アイコン（実行中はスピナー、完了は ● ）
- 日本語ラベル
- 引数の JSON 文字列
- ツール実行結果のプレビュー（最大 6 行）

## 動作確認

```bash
uv sync
uv run python -c "from modules.aws_knowledge import get_aws_knowledge_tools; \
    print([t.name for t in get_aws_knowledge_tools()])"
# => ['aws___read_documentation', 'aws___search_documentation', 'aws___recommend']
```

Flask 起動確認:

```bash
uv run python -c "from src.app import app; \
    print(app.test_client().get('/').get_json())"
# => {'message': 'Hello world.'}
```

## 未対応 / 補足

- MAX_TOOL_ITERATIONS は 5 固定（必要なら環境変数化）
- MCP クライアントは毎回新規生成（HTTP セッション再利用は langchain-mcp-adapters に委譲）
- 思考トークン (adaptive thinking) と tool_use の併用は Vertex AI 経由でもサポート
