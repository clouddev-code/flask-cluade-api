from typing import Any

import google.auth
import google.auth.transport.requests
from  langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import openai
import base64
import uuid
from pydantic import SecretStr

class OpenAICredentialsRefresher:
    def __init__(self, **kwargs: Any) -> None:
        # Set a dummy key here
        self.client = openai.OpenAI(**kwargs, api_key="672e5906-d517-4c58-9d06-967e4dc00fea:HquhuW2JfiB4K/36iEny8OyO1lVaVYORXjHCXMmj")

    def __getattr__(self, name: str) -> Any:
        return getattr(self.client, name)

 


LOCATION="global"
#LOCATION="us-east5"

accept = 'application/json'
contentType = 'application/json'

client = OpenAICredentialsRefresher(base_url="https://api.ai.sakura.ad.jp/v1")

def chatcompletion(userMessage:str) -> str:
    prompt = ChatPromptTemplate.from_messages([
        ("human", "{input}")
    ])

    llm = ChatOpenAI(
        base_url="https://api.ai.sakura.ad.jp/v1",
        max_tokens=2000
    )

    try:
        chain =   prompt | llm | StrOutputParser()
        # outputText = chain.invoke({"input":userMessage}, config={"callbacks": [langfuse_handler],"run_id": predefined_run_id,})
        outputText = chain.invoke({"input":userMessage})
    except Exception as error:
        raise error
    # ユーザーからのメッセージを受け取る
    return outputText


def chatcompletion_stream(userMessage: str):
    """
     ストリーミング用のチャット完了関数
     LangChainのstreamメソッドを使用してジェネレーターを返す
     """
    predefined_run_id = str(uuid.uuid4())
    prompt = ChatPromptTemplate.from_messages([
        ("human", "{input}")
    ])

    llm = ChatOpenAI(
        base_url="https://api.ai.sakura.ad.jp/v1",
        model="gpt-oss-120b",
        max_tokens=2000,
        stream_usage=True,
        api_key=SecretStr("672e5906-d517-4c58-9d06-967e4dc00fea:HquhuW2JfiB4K/36iEny8OyO1lVaVYORXjHCXMmj")
    )

    try:
        chain = prompt | llm | StrOutputParser()
        # streamメソッドを使ってチャンクごとに結果を生成
        for chunk in chain.stream({"input": userMessage}):
            yield chunk
    except Exception as error:
        raise error

