# Next.js Streaming対応チャットUIアプリ

このプロジェクトは、Flask APIのSSE（Server-Sent Events）ストリーミングに対応したNext.jsチャットUIアプリです。

## 機能

- ✅ **リアルタイムストリーミング**: SSEを使用したLLMレスポンスのリアルタイム表示
- ✅ **会話履歴保存**: LocalStorageに会話を自動保存、ページリロード後も復元
- ✅ **モダンUI**: Tailwind CSSによるレスポンシブでモダンなデザイン
- ✅ **TypeScript**: 型安全な開発
- ✅ **App Router**: Next.js 15の最新App Routerを使用

## プロジェクト構造

```
frontend/
├── app/                      # Next.js App Router
│   ├── page.tsx              # メインページ
│   ├── layout.tsx            # ルートレイアウト
│   └── globals.css           # グローバルスタイル
├── components/               # UIコンポーネント
│   ├── Chat.tsx              # チャットコンテナ
│   ├── MessageList.tsx       # メッセージリスト
│   ├── Message.tsx           # メッセージアイテム
│   └── ChatInput.tsx         # 入力フォーム
├── hooks/
│   └── useChat.ts            # チャットロジック（SSE接続・履歴管理）
├── lib/
│   └── storage.ts            # LocalStorage操作
└── types/
    └── chat.ts               # 型定義
```

## セットアップ

### 1. 依存関係のインストール

```bash
npm install
```

### 2. 環境変数の設定

`.env.local` ファイルが作成されています。Flask APIのURLを確認してください：

```env
NEXT_PUBLIC_API_URL=http://localhost:5000
```

必要に応じてURLを変更してください。

### 3. Flask APIの起動

まず、Flask APIを起動します（別のターミナルで）：

```bash
cd ../flask-cloud-api
python -m src.app
```

または、Flaskアプリの起動方法に従ってください。

### 4. 開発サーバーの起動

```bash
npm run dev
```

ブラウザで [http://localhost:3000](http://localhost:3000) を開いてください。

## 使い方

1. テキストエリアにメッセージを入力
2. **送信**ボタンをクリック、または **Enter**キーを押す
   - **Shift + Enter**で改行
3. AIのレスポンスがリアルタイムでストリーミング表示されます
4. 会話履歴は自動的にLocalStorageに保存されます
5. **クリア**ボタンで会話履歴を削除できます

## API仕様

### エンドポイント

```
POST http://localhost:5000/api/chat/stream
```

### リクエスト

```json
{
  "message": {
    "text": "ユーザーメッセージ"
  }
}
```

### レスポンス（SSE形式）

```
data: {"chunk": "こ", "text": "こ"}
data: {"chunk": "ん", "text": "こん"}
data: {"chunk": "に", "text": "こんに"}
data: {"chunk": "ち", "text": "こんにち"}
data: {"chunk": "は", "text": "こんにちは"}
data: {"done": true, "text": "こんにちは"}
```

## ビルド

本番用ビルド：

```bash
npm run build
npm start
```

## トラブルシューティング

### CORSエラーが発生する場合

Flask APIでCORSが有効になっていることを確認してください：

```python
from flask_cors import CORS
CORS(app)
```

### APIに接続できない場合

1. Flask APIが起動していることを確認
2. `.env.local`のURLが正しいことを確認
3. ブラウザの開発者ツールでネットワークタブを確認

### 会話履歴が保存されない場合

- ブラウザのLocalStorageが有効になっていることを確認
- プライベートブラウジングモードでは動作しない場合があります

## 技術スタック

- **Next.js 15** - Reactフレームワーク
- **React 19** - UIライブラリ
- **TypeScript** - 型安全性
- **Tailwind CSS** - スタイリング
- **Fetch API** - SSE通信

## ライセンス

MIT
