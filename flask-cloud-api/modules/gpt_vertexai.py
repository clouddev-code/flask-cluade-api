from typing import Any

import google.auth
import google.auth.transport.requests
import openai
import base64

class OpenAICredentialsRefresher:
    def __init__(self, **kwargs: Any) -> None:
        # Set a dummy key here
        self.client = openai.OpenAI(**kwargs, api_key="")

    def __getattr__(self, name: str) -> Any:
        return getattr(self.client, name)

 


LOCATION="global"
#LOCATION="us-east5"

accept = 'application/json'
contentType = 'application/json'

client = OpenAICredentialsRefresher(base_url="https://api.ai.sakura.ad.jp/v1")

def chatcompletion(userMessage:str) -> str:


    stream = client.chat.completions.create(
        model="gpt-oss-120b",
        messages=[
            {
                "role": "user",
                "content": userMessage
            }
        ],
        stream=True,
        reasoning_effort="medium"
    )
    try:

    except Exception as error:
        raise error
    # ユーザーからのメッセージを受け取る
    return outputText


def chatcompletion_stream(userMessage: str):
    """
    ストリーミング用のチャット完了関数
    LangChainのstreamメソッドを使用してジェネレーターを返す
    """


    stream = client.chat.completions.create(
        model="gpt-oss-120b",
        messages=[
            {
                "role": "user",
                "content": userMessage
            }
        ],
        stream=True,
        reasoning_effort="medium"
    )

    try:
        for chunk in chain.stream({"input": userMessage}):
            yield chunk
    except Exception as error:
        raise error

