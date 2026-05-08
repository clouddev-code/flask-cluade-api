from langchain_core.messages import HumanMessage
from langchain_aws import ChatBedrock, ChatBedrockConverse


def chatcompletion(userMessage: str) -> str:
    llm = ChatBedrock(
        model="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        max_tokens=1025,
        model_kwargs={"thinking": {"type": "enabled", "budget_tokens": 1024}},
        region_name="us-west-2"
    )
    try:
        response = llm.invoke([HumanMessage(content=userMessage)])
        return response.content
    except Exception as error:
        raise error


def chatcompletion_stream(userMessage: str):
    """ストリーミングでチャット応答を生成"""
    llm = ChatBedrockConverse(
        model="global.anthropic.claude-opus-4-5-20251101-v1:0",
        max_tokens=10250,
        additional_model_request_fields={"thinking": {"type": "enabled", "budget_tokens": 10240}},
        region_name="us-west-2"
    )
    try:
        for chunk in llm.stream([HumanMessage(content=userMessage)]):
            yield chunk.content
    except Exception as error:
        raise error
