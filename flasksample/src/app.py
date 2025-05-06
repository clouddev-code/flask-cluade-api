from flask import Flask
from flask import Flask, request, jsonify, Response
from flask_restful import Resource, Api
from flask_cors import CORS
from schemas import (
    ChatRequest,
    ChatResponse,
)
from modules.claude_client import chatcompletion
from prometheus_flask_exporter import PrometheusMetrics



# flask app
app = Flask(__name__)
metrics = PrometheusMetrics(app)

# static information as metric
metrics.info('app_info', 'Application info', version='1.0.3')

@app.route('/')
@metrics.do_not_track()
def hello():
    return {'message': 'Hello world.'}


@app.route('/api/chat',methods=['POST'])
@metrics.do_not_track()
@metrics.summary(
    'requests_by_status', 'Request latencies by status',
    labels={'status': lambda r: r.status_code}
)
@metrics.histogram('requests_latency_seconds', 'Request latency',
                   labels={'status': lambda r: r.status_code, 'path': lambda: request.path})
def chat():
    try:
        # リクエストボディからデータを取得
        req = request.get_json()
        if not req:
            return jsonify({"error": "Invalid JSON"}), 400
            
        # リクエストの形式を確認
        try:
            data = ChatRequest(**req)
        except Exception as e:
            app.logger.error(f"Validation error: {str(e)}")
            return jsonify({"error": "Invalid request format", "details": str(e)}), 400

        # メッセージの存在チェック
        if not data.message or not data.message.get('argumentText'):
            return jsonify({"error": "Message argument text is required"}), 400

        # Claudeにリクエストを送信
        result = chatcompletion(data.message['argumentText'])
        
        # エラーチェック
        if "error" in result:
            error_status = result.get("status", "unknown_error")
            
            # エラータイプに応じたHTTPステータスコードをマッピング
            status_code_mapping = {
                "input_error": 400,
                "validation_error": 400,
                "timeout_error": 504,
                "model_not_ready": 503,
                "throttling_error": 429,
                "access_denied": 403,
                "api_error": 502,
                "format_error": 502,
                "parse_error": 502,
                "processing_error": 500,
                "unknown_error": 500
            }
            
            status_code = status_code_mapping.get(error_status, 500)
            return jsonify({"error": result["error"], "status": error_status}), status_code

        # 成功レスポンスの処理
        if "completion" in result:
            cards = {
                "text": result["completion"]
            }
            return jsonify(cards), 200
        else:
            # 想定外のレスポンス形式
            return jsonify({"error": "Unexpected response format"}), 500
            
    except Exception as e:
        app.logger.error(f"Unexpected error in chat endpoint: {str(e)}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500
