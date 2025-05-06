from langchain.chat_models import AzureChatOpenAI
from langchain.schema import (
    SystemMessage,
    HumanMessage,
    AIMessage,
)

import os
import boto3
import json

bedrock_runtime = boto3.client(
    service_name='bedrock-runtime',
    region_name='ap-northeast-1'
)

modelId = 'anthropic.claude-3-7-sonnet-20240229-v1:0' 
accept = 'application/json'
contentType = 'application/json'

def chatcompletion(userMessage:str) -> str:
  

    # 推論実行
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 500,
        "messages": [
            {
                "role": "user",
                "content": userMessage
            }
        ]
    })

    response = bedrock_runtime.invoke_model(
    	modelId=modelId,
    	accept=accept,
    	contentType=contentType,
        body=body
    )
    response_body = json.loads(response.get('body').read())
    return response_body["content"][0]["text"]

