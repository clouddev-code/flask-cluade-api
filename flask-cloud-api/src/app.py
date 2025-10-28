from flask import Flask, request, jsonify, Response, stream_with_context
from flask_restful import Resource, Api
from flask_cors import CORS
from schemas import (
    ChatRequest,
    ChatResponse,
)
# from modules.gemini_vertexai import chatcompletion
from modules.cloud3_vertexai import chatcompletion, chatcompletion_stream
import json
# flask app
app = Flask(__name__)
CORS(app)


@app.route('/')
def hello():
    return {'message': 'Hello world.'}


@app.route('/api/chat',methods=['POST'])
def chat():
    # リクエストボディからデータを取得
    req = request.get_json(silent=True)


    # Google Chatのメッセージを取得
    user_message = req.get('message', {}).get('text', '')

    # メッセージがない場合はエラーレスポンスを返す
    if not user_message:
        return jsonify({'error': 'No message text provided'}), 400

    # リクエストの形式を確認
    #data = ChatRequest(**req)

    # OpenAIにリクエストを送信
    result = chatcompletion(user_message)

    # res = ChatResponse(message=result)

    cards = {
         "text": result
    }
    # res = ChatResponse(cards=cards)

    # レスポンスを返却
    return cards


@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """
    ストリーミング対応のチャットエンドポイント
    Server-Sent Events (SSE) 形式でレスポンスを返す
    """
    # リクエストボディからデータを取得
    req = request.get_json(silent=True)

    # Google Chatのメッセージを取得
    user_message = req.get('message', {}).get('text', '')

    # メッセージがない場合はエラーレスポンスを返す
    if not user_message:
        return jsonify({'error': 'No message text provided'}), 400

    def generate():
        """
        ストリーミング用のジェネレーター関数
        Server-Sent Events (SSE) 形式でデータを送信
        """
        try:
            full_text = ""
            for chunk in chatcompletion_stream(user_message):
                full_text += chunk
                # SSE形式でデータを送信
                # data: で始まる行がイベントデータ
                yield f"data: {json.dumps({'chunk': chunk, 'text': full_text})}\n\n"

            # ストリーム終了を通知
            yield f"data: {json.dumps({'done': True, 'text': full_text})}\n\n"
        except Exception as e:
            # エラーが発生した場合
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    # Server-Sent Events形式でレスポンスを返す
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # nginx バッファリング無効化
            'Connection': 'keep-alive'
        }
    )
