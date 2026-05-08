from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr


def chatcompletion(userMessage: str) -> str:
    llm = ChatOpenAI(
        base_url="https://api.ai.sakura.ad.jp/v1",
        model="gpt-oss-120b",
        max_tokens=2000,
        stream_usage=False,
        api_key=SecretStr("7ae09f33-b704-4cb1-afae-4a3a254ae28c:i69imZCJKd0M00JmD1ORR2dtXXtZNjrUH0iJIfJV")
    )
    try:
        response = llm.invoke([HumanMessage(content=userMessage)])
        return response.content
    except Exception as error:
        raise error


def chatcompletion_stream(userMessage: str):
    """
    ストリーミング用のチャット完了関数
    """
    llm = ChatOpenAI(
        base_url="https://api.ai.sakura.ad.jp/v1",
        model="gpt-oss-120b",
        max_tokens=2000,
        stream_usage=True,
        api_key=SecretStr("7ae09f33-b704-4cb1-afae-4a3a254ae28c:i69imZCJKd0M00JmD1ORR2dtXXtZNjrUH0iJIfJV")
    )
    try:
        for chunk in llm.stream([HumanMessage(content=userMessage)]):
            yield chunk.content
    except Exception as error:
        raise error
