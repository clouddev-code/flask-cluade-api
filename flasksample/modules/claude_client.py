from langchain.chat_models import AzureChatOpenAI
from langchain.schema import (
    SystemMessage,
    HumanMessage,
    AIMessage,
)

import os
import boto3
import json

bedrock_runtime = boto3.client(
    service_name='bedrock-runtime',
    region_name='ap-northeast-1'
)

modelId = 'anthropic.claude-v2:1' 
accept = 'application/json'
contentType = 'application/json'

def chatcompletion(userMessage:str) -> dict:
    """
    Perform a chat completion using AWS Bedrock Anthropic Claude model
    
    Args:
        userMessage: The user's input message
        
    Returns:
        dict: Response with completion text or error information
    """
    try:
        # Validate input
        if not userMessage or not isinstance(userMessage, str):
            return {"error": "Invalid input message", "status": "input_error"}
            
        # Prepare request body
        body = json.dumps({
            "prompt": '\n\nHuman:{0}\n\nAssistant:'.format(userMessage),
            "max_tokens_to_sample": 500,
        })

        # Call the Bedrock API
        try:
            response = bedrock_runtime.invoke_model(
                modelId=modelId,
                accept=accept,
                contentType=contentType,
                body=body
            )
        except bedrock_runtime.exceptions.ModelTimeoutException:
            return {"error": "Model inference timed out", "status": "timeout_error"}
        except bedrock_runtime.exceptions.ValidationException:
            return {"error": "Invalid request parameters", "status": "validation_error"}
        except bedrock_runtime.exceptions.ModelNotReadyException:
            return {"error": "Model is not ready for inference", "status": "model_not_ready"}
        except bedrock_runtime.exceptions.ThrottlingException:
            return {"error": "API rate limit exceeded", "status": "throttling_error"}
        except bedrock_runtime.exceptions.AccessDeniedException:
            return {"error": "Access denied to the model", "status": "access_denied"}
        except Exception as e:
            return {"error": f"AWS Bedrock API error: {str(e)}", "status": "api_error"}
        
        # Process response
        try:
            response_body = json.loads(response.get('body').read())
            if "completion" not in response_body:
                return {"error": "Unexpected API response format", "status": "format_error"}
            return {"completion": response_body["completion"], "status": "success"}
        except json.JSONDecodeError:
            return {"error": "Failed to parse API response", "status": "parse_error"}
        except Exception as e:
            return {"error": f"Error processing response: {str(e)}", "status": "processing_error"}
            
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}", "status": "unknown_error"}

