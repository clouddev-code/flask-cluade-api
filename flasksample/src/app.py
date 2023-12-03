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
    # リクエストボディからデータを取得
    req = request.get_json()

    # リクエストの形式を確認
    data = ChatRequest(**req)

 

    # OpenAIにリクエストを送信
    result = chatcompletion(data.message['argumentText'])

    res = ChatResponse(message=result)
    
    # レスポンスを返却
    return jsonify(res.dict())