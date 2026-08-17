import json

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

from modules.cloud3_bedrock import chatcompletion, chatcompletion_stream
from modules.session_store import session_store

app = Flask(__name__)
CORS(app)


def _extract_user_message(req: dict | None) -> tuple[str, str | None]:
    """リクエストから user_message と session_id を取り出す。"""
    if not isinstance(req, dict):
        return "", None
    user_message = (req.get("message") or {}).get("text", "") or ""
    session_id = req.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        session_id = None
    return user_message.strip(), session_id


@app.route('/')
def hello():
    return {'message': 'Hello world.'}


@app.route('/api/chat', methods=['POST'])
def chat():
    req = request.get_json(silent=True)
    user_message, session_id = _extract_user_message(req)

    if not user_message:
        return jsonify({'error': 'No message text provided'}), 400

    session_id = session_store.ensure_session(session_id)
    history = session_store.get_messages(session_id)

    text, thinking = chatcompletion(user_message, history=history)

    session_store.append(session_id, "user", user_message)
    session_store.append(session_id, "assistant", text)

    return {
        "text": text,
        "thinking": thinking,
        "session_id": session_id,
    }


@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """
    ストリーミング対応のチャットエンドポイント
    Server-Sent Events (SSE) 形式でレスポンスを返す
    """
    req = request.get_json(silent=True)
    user_message, session_id = _extract_user_message(req)

    if not user_message:
        return jsonify({'error': 'No message text provided'}), 400

    session_id = session_store.ensure_session(session_id)
    history = session_store.get_messages(session_id)

    def generate():
        full_text = ""
        full_thinking = ""
        try:
            yield f"data: {json.dumps({'session_id': session_id})}\n\n"

            for kind, chunk in chatcompletion_stream(user_message, history=history):
                if kind == "thinking":
                    full_thinking += chunk
                elif kind == "text":
                    full_text += chunk
                # tool_use / tool_result はイベント通知のみで本文には含めない
                payload = {
                    "kind": kind,
                    "chunk": chunk,
                    "text": full_text,
                    "thinking": full_thinking,
                }
                yield f"data: {json.dumps(payload)}\n\n"

            session_store.append(session_id, "user", user_message)
            session_store.append(session_id, "assistant", full_text)

            done_payload = {
                "done": True,
                "text": full_text,
                "thinking": full_thinking,
                "session_id": session_id,
            }
            yield f"data: {json.dumps(done_payload)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'session_id': session_id})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )


@app.route('/api/chat/reset', methods=['POST'])
def chat_reset():
    """指定された session_id の会話履歴を破棄する。"""
    req = request.get_json(silent=True) or {}
    session_id = req.get("session_id")
    if isinstance(session_id, str) and session_id:
        session_store.reset(session_id)
    return {"ok": True}
