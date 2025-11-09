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



accept = 'application/json'
contentType = 'application/json'


def chatcompletion(userMessage:str) -> str:
    prompt = ChatPromptTemplate.from_messages([
        ("human", "{input}")
    ])

    llm = ChatOpenAI(
         base_url="https://api.ai.sakura.ad.jp/v1",
        model="gpt-oss-120b",
        max_tokens=2000,
        stream_usage=False,
        api_key=SecretStr("")
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
        api_key=SecretStr("")
    )

    try:
        chain = prompt | llm | StrOutputParser()
        # streamメソッドを使ってチャンクごとに結果を生成
        for chunk in chain.stream({"input": userMessage}):
            yield chunk
    except Exception as error:
        raise error

