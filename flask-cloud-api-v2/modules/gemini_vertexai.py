from langchain_core.messages import HumanMessage
from langchain_google_vertexai import ChatVertexAI

LOCATION = "global"


def chatcompletion(userMessage: str) -> str:
    llm = ChatVertexAI(
        model="gemini-2.5-pro",
        temperature=0,
        max_tokens=None,
        max_retries=2,
        stop=None,
        location=LOCATION,
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
    llm = ChatVertexAI(
        model="gemini-3-pro-preview",
        temperature=0,
        max_tokens=None,
        max_retries=2,
        stop=None,
        location=LOCATION,
    )
    try:
        for chunk in llm.stream([HumanMessage(content=userMessage)]):
            yield chunk.content
    except Exception as error:
        raise error
