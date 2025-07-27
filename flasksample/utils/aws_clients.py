import boto3
from botocore.client import Config


class AWSClientManager:
    _bedrock_clients = {}
    _s3_clients = {}
    
    @classmethod
    def get_bedrock_client(cls, region_name='ap-northeast-1'):
        if region_name not in cls._bedrock_clients:
            cls._bedrock_clients[region_name] = boto3.client(
                service_name='bedrock-runtime',
                region_name=region_name
            )
        return cls._bedrock_clients[region_name]
    
    @classmethod
    def get_s3_client(cls, region_name='ap-northeast-1', use_v4_signature=False):
        key = f"{region_name}_{use_v4_signature}"
        if key not in cls._s3_clients:
            if use_v4_signature:
                config = Config(signature_version='s3v4')
                cls._s3_clients[key] = boto3.client('s3', config=config, region_name=region_name)
            else:
                cls._s3_clients[key] = boto3.client('s3', region_name=region_name)
        return cls._s3_clients[key]


def generate_presigned_url(filename, bucket_name, object_key, expiration=86400, region='ap-northeast-1', use_v4_signature=False):
    s3_client = AWSClientManager.get_s3_client(region, use_v4_signature)
    
    s3_client.upload_file(filename, bucket_name, object_key)
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket_name, 'Key': object_key},
        ExpiresIn=expiration
    )
    return url
