from langchain_core.messages import HumanMessage
from langchain_google_vertexai.model_garden import ChatAnthropicVertex
import uuid

LOCATION = "global"

def chatcompletion(userMessage: str) -> str:
    llm = ChatAnthropicVertex(
        project="",
        location=LOCATION,
        model_name="claude-sonnet-4-6",
        max_tokens=2000,
        model_kwargs={
            "thinking": {
                "type": "enabled",
                "budget_tokens": 1600
            }
        }
    )
    try:
        response = llm.invoke([HumanMessage(content=userMessage)])
        content = response.content
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            return "".join(
                block.get("text", "") for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        return str(content)
    except Exception as error:
        raise error


def chatcompletion_stream(userMessage: str):
    """
    ストリーミング用のチャット完了関数
    """
    llm = ChatAnthropicVertex(
        project="",
        location=LOCATION,
        model_name="claude-sonnet-4-6",
        max_tokens=2000,
        model_kwargs={
            "thinking": {
                "type": "enabled",
                "budget_tokens": 1600
            }
        }
    )
    try:
        for chunk in llm.stream([HumanMessage(content=userMessage)]):
            content = chunk.content
            if isinstance(content, str):
                yield content
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        yield block.get("text", "")
    except Exception as error:
        raise error
