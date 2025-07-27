import os
import json
import base64
from PIL import Image
from io import BytesIO
import pyshorteners
import sys
sys.path.append('/home/ubuntu/flask-cluade-api')
from flasksample.utils.aws_clients import AWSClientManager, generate_presigned_url

modelId = 'anthropic.claude-v2:1' 
accept = 'application/json'
contentType = 'application/json'



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

    bedrock_runtime = AWSClientManager.get_bedrock_client('us-west-2')
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
    presigned_url = generate_presigned_url('chihuahua.png', bucket_name, 'chihuahua.png', region='ap-northeast-1', use_v4_signature=True)
    shortener = pyshorteners.Shortener()
    presigned_short_url = shortener.tinyurl.short(presigned_url)

    # response_body = json.loads(response.get('body').read())
    return presigned_short_url

