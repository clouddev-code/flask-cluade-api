from langchain_core.messages.ai import AIMessage
from langchain_core.messages.system import SystemMessage
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_aws import ChatBedrock
import os
from langfuse.decorators import observe
import json


from langfuse.callback import CallbackHandler
langfuse_handler = CallbackHandler(
    public_key="pk-lf-843e1baa-3875-4a03-aa06-6a1dd922c102",
    secret_key="sk-lf-8d064dde-bafb-4392-8042-09fb0ee8bd6f",
    host="https://us.cloud.langfuse.com"
)

 




accept = 'application/json'
contentType = 'application/json'

def chatcompletion(userMessage:str) -> str:

    prompt = ChatPromptTemplate.from_messages([
         ("human","{input}")
    ])


    llm = ChatBedrock(
        model="us.anthropic.claude-sonnet-4-20250514-v1:0",
        max_tokens=1025,  # budget_tokensよりも値
        model_kwargs={"thinking": {"type": "enabled", "budget_tokens": 1024}},
        region_name="us-west-2"
    )

    try:
        chain =   prompt | llm | StrOutputParser()
        outputText = chain.invoke({"input":userMessage}, config={"callbacks": [langfuse_handler]})

    except Exception as error:
        raise error
    # ユーザーからのメッセージを受け取る
    return outputText


def chatcompletion_stream(userMessage: str):
    """ストリーミングでチャット応答を生成"""
    prompt = ChatPromptTemplate.from_messages([
         ("human","{input}")
    ])

    llm = ChatBedrock(
        model="us.anthropic.claude-sonnet-4-20250514-v1:0",
        max_tokens=1025,
        model_kwargs={"thinking": {"type": "enabled", "budget_tokens": 1024}},
        region_name="us-west-2",
        streaming=True
    )

    try:
        chain = prompt | llm | StrOutputParser()
        for chunk in chain.stream({"input": userMessage}, config={"callbacks": [langfuse_handler]}):
            yield chunk
    except Exception as error:
        raise error

