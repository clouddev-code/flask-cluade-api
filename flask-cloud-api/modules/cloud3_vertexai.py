from langchain_core.messages.ai import AIMessage
from langchain_core.messages.system import SystemMessage
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_google_vertexai.model_garden import ChatAnthropicVertex
from langchain_core.output_parsers import StrOutputParser
import os
#from langfuse.decorators import observe
import json
import uuid

#from langfuse.callback import CallbackHandler
#langfuse_handler = CallbackHandler(
#    public_key="pk-lf-843e1baa-3875-4a03-aa06-6a1dd922c102",
#    secret_key="sk-lf-8d064dde-bafb-4392-8042-09fb0ee8bd6f",
#    host="https://us.cloud.langfuse.com"
#)

 


LOCATION="global"
#LOCATION="us-east5"

accept = 'application/json'
contentType = 'application/json'

def chatcompletion(userMessage:str) -> str:

    predefined_run_id = str(uuid.uuid4())
    prompt = ChatPromptTemplate.from_messages([
         ("human","{input}")
    ])


    llm = ChatAnthropicVertex(
        project="",
        location=LOCATION,
        model_name="claude-sonnet-4-5@20250929",
        max_tokens=2000,
        model_kwargs={  # Enable Thinking Mode
            "thinking": {
                "type": "enabled",
                "budget_tokens": 1600
            }
        }
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
         ("human","{input}")
    ])

    llm = ChatAnthropicVertex(
        project="",
        location=LOCATION,
        model_name="claude-sonnet-4-5@20250929",
        max_tokens=2000,
        model_kwargs={  # Enable Thinking Mode
            "thinking": {
                "type": "enabled",
                "budget_tokens": 1600
            }
        }
    )

    try:
        chain = prompt | llm | StrOutputParser()
        # streamメソッドを使ってチャンクごとに結果を生成
        for chunk in chain.stream({"input": userMessage}):
            yield chunk
    except Exception as error:
        raise error

