import os
import json
from ..utils.aws_clients import AWSClientManager

modelId = 'anthropic.claude-v2:1' 
accept = 'application/json'
contentType = 'application/json'

def chatcompletion(userMessage:str) -> str:
  

    # 推論実行
    body = json.dumps({
        "prompt": '\n\nHuman:{0}\n\nAssistant:'.format(userMessage),
        "max_tokens_to_sample": 500,
    })

    bedrock_runtime = AWSClientManager.get_bedrock_client('ap-northeast-1')
    response = bedrock_runtime.invoke_model(
    	modelId=modelId,
    	accept=accept,
    	contentType=contentType,
        body=body
    )
    response_body = json.loads(response.get('body').read())
    return response_body["completion"]

