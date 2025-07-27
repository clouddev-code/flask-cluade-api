import asyncio
from strands import Agent, tool
from strands.models import BedrockModel
import boto3
import json
import os

bedrock_runtime = boto3.client(
    service_name='bedrock-runtime',
    region_name='ap-northeast-1'
)

bedrock_model = BedrockModel(
    model_id="anthropic.claude-v2:1",
    region_name="ap-northeast-1"
)

@tool
def text_chat_tool(query: str) -> str:
    """Claude v2:1を使用したテキスト推論ツール"""
    body = json.dumps({
        "prompt": '\n\nHuman:{0}\n\nAssistant:'.format(query),
        "max_tokens_to_sample": 500,
    })
    
    response = bedrock_runtime.invoke_model(
        modelId="anthropic.claude-v2:1",
        accept="application/json",
        contentType="application/json",
        body=body
    )
    response_body = json.loads(response.get('body').read())
    return response_body["completion"]

agent = Agent(
    model=bedrock_model,
    tools=[text_chat_tool],
    name="Claude Chat Agent",
    description="AWS BedrockのClaude v2:1を使用したチャットエージェント"
)

async def process_chat_with_strand_agent(message: str) -> str:
    """Strand Agentを使用したチャット処理"""
    try:
        result = await agent.invoke_async(message)
        return result.content if hasattr(result, 'content') else str(result)
    except Exception as e:
        return text_chat_tool(message)

def process_chat_sync(message: str) -> str:
    """同期版のチャット処理（既存のFlask互換性のため）"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(process_chat_with_strand_agent(message))
        loop.close()
        return result
    except Exception as e:
        from .claude_client import chatcompletion
        return chatcompletion(message)
