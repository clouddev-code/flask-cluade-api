from langchain.chat_models import AzureChatOpenAI
from langchain.schema import (
    SystemMessage,
    HumanMessage,
    AIMessage,
)

import os
import boto3
import json
import base64
from PIL import Image
from io import BytesIO
from botocore.client import Config
import pyshorteners

bedrock_runtime = boto3.client(
    service_name='bedrock-runtime',
    region_name='us-west-2'
)

modelId = 'anthropic.claude-v2:1' 
accept = 'application/json'
contentType = 'application/json'


def generate_presigned_url(filename, bucket_name, object_key, expiration=86400, region='ap-northeast-1'):
    s3_client = boto3.client('s3', config=Config(signature_version='s3v4'), region_name=region)

    s3_client.upload_file(filename, bucket_name, object_key)
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket_name, 'Key': object_key},
        ExpiresIn=expiration
    )
    return url

def chatcompletion(userMessage:str) -> str:
  

    # 推論実行
    body = json.dumps(
        {
            "taskType": "TEXT_IMAGE",
            "textToImageParams": {
                "text": userMessage,  # Required
                #           "negativeText": "<text>"  # Optional
            },
            "imageGenerationConfig": {
                "numberOfImages": 1,  # Range: 1 to 5
                "quality": "premium",  # Options: standard or premium
                "height": 768,  # Supported height list in the docs
                "width": 1280,  # Supported width list in the docs
                "cfgScale": 7.5,  # Range: 1.0 (exclusive) to 10.0
                "seed": 42  # Range: 0 to 214783647
            }
        }
    )

    response = bedrock_runtime.invoke_model(
        body=body,
        modelId="amazon.titan-image-generator-v1",
        accept="application/json",
        contentType="application/json"
    )
    response_body = json.loads(response.get("body").read())
    images = [Image.open(BytesIO(base64.b64decode(base64_image))) for base64_image in response_body.get("images")]

    for idx, img in enumerate(images):
        img.save(f"chihuahua.png", quality=100)


    # S3バケットとオブジェクトキーを指定
    bucket_name = 's3b-image-upload-storage-ap-northeast-1'

    # 署名付きURLの生成とURL短縮化
    presigned_url = generate_presigned_url('chihuahua.png',bucket_name, 'chihuahua.png')
    shortener = pyshorteners.Shortener()
    presigned_short_url = shortener.tinyurl.short(presigned_url)

    # response_body = json.loads(response.get('body').read())
    return presigned_short_url

