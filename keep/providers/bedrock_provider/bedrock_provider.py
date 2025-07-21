import json
import dataclasses
import pydantic
import boto3
import os

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.exceptions.provider_exception import ProviderException
import logging

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class BedrockProviderAuthConfig:
    access_key: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Bedrock Access Token (Leave empty if using IAM role at EC2)",
            "sensitive": True,
        },
    )

    secret_access_key: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Bedrock Secret Access Token (Leave empty if using IAM role at EC2)",
            "sensitive": True,
        },
    )

    region: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "The AWS region name where Bedrock is available (Leave empty if using IAM role at EC2)",
            "sensitive": True,
        },
    )


class BedrockProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Bedrock"
    PROVIDER_CATEGORY = ["AI"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = BedrockProviderAuthConfig(**self.config.authentication)
        
        # Use SSO session if access keys are None
        if self.authentication_config.access_key is None:
            aws_profile = os.getenv('AWS_PROFILE', 'default')
            session = boto3.Session(profile_name=aws_profile)
            bedrock_mgmt_client = session.client(
                "bedrock",
                region_name=self.authentication_config.region,
            )
        else:
            bedrock_mgmt_client = boto3.client(
                "bedrock",
                aws_access_key_id=self.authentication_config.access_key,
                aws_secret_access_key=self.authentication_config.secret_access_key,
                region_name=self.authentication_config.region,
            )
        try:
            response = bedrock_mgmt_client.list_foundation_models()
            if response.get("modelSummaries"):
                logger.info(
                    f"Validation successful. Found at least one model: {response['modelSummaries'][0]['modelId']}"
                )
            else:
                logger.info(
                    "Validation successful (connected), but no foundation models listed (check region/permissions?)."
                )

        except Exception as e:
            raise ProviderException(f"Failed to list Foundational Models {e}")

    def dispose(self):
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {}
        return scopes

    def _query(
        self,
        prompt,
        model="meta.llama3-3-70b-instruct-v1:0",
        max_tokens=1024,
        temperature=0.7,
        top_p=0.9,
        structured_output_format=None,
    ):
        try:
            # Get Bedrock client (create if not already initialized)
            if self.authentication_config.access_key is None:
                aws_profile = os.getenv('AWS_PROFILE', 'default')
                session = boto3.Session(profile_name=aws_profile)
                bedrock = session.client(
                    service_name="bedrock-runtime",
                    region_name=self.authentication_config.region,
                )
            else:
                bedrock = boto3.client(
                    service_name="bedrock-runtime",
                    region_name=self.authentication_config.region,
                    aws_access_key_id=self.authentication_config.access_key,
                    aws_secret_access_key=self.authentication_config.secret_access_key,
                )

            system_prompt_content = ""
            user_prompt = prompt

            # Prepare system prompt content if structured output is needed
            if structured_output_format:
                system_prompt_content = (
                    f"You must respond ONLY with valid JSON that strictly matches the following JSON Schema. "
                    f"Do not include any other explanatory text, commentary, or markdown formatting.\n"
                    f"JSON Schema:\n```json\n{json.dumps(structured_output_format, indent=2)}\n```\n"
                )
                # Note: For Claude Messages API, this system prompt goes in a dedicated 'system' field.
                # For other models, we might need to prepend it to the user prompt as before.

            request_body = {}
            model_family = "unknown"

            # --- Anthropic Claude (Messages API) ---
            if "claude" in model.lower() and "anthropic" in model.lower():
                model_family = "anthropic_messages"
                messages = [{"role": "user", "content": user_prompt}]  # Start with user prompt

                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",  # Required for Messages API
                    "max_tokens": max_tokens,  # Parameter name change
                    "messages": messages,
                    "temperature": temperature,
                    "top_p": top_p,
                }
                # Add system prompt if provided
                if system_prompt_content:
                    request_body["system"] = system_prompt_content

            # --- Meta Llama ---
            elif "meta" in model.lower() or "llama" in model.lower():
                model_family = "meta"
                if system_prompt_content:
                    final_prompt = f"{system_prompt_content}\nUser query: {user_prompt}"
                else:
                    final_prompt = user_prompt

                request_body = {
                    "prompt": final_prompt,
                    "max_gen_len": max_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                }

            # --- Amazon Titan Text ---
            elif "titan" in model.lower() and "amazon" in model.lower():
                model_family = "amazon_titan_text"
                if system_prompt_content:
                    final_prompt = f"{system_prompt_content}\nUser query: {user_prompt}"
                else:
                    final_prompt = user_prompt

                request_body = {
                    "inputText": final_prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": max_tokens,
                        "stopSequences": [],
                        "temperature": temperature,
                        "topP": top_p,
                    },
                }

            # Add elif blocks here for other model families (e.g., Cohere, AI21) as needed

            if not request_body:
                raise ValueError(f"Unsupported model family or model ID: {model}. Please add specific handling.")

            body_json = json.dumps(request_body)
            logger.info(f"Invoking model {model} in region {bedrock.meta.region_name}")

            # Invoke the Bedrock model
            response = bedrock.invoke_model(
                modelId=model,
                body=body_json,
                accept="application/json",
                contentType="application/json",
            )

            # Parse the response stream
            response_body_raw = response["body"].read()
            response_body = json.loads(response_body_raw.decode("utf-8"))
            # logging.debug(f"Raw Response Body: {response_body}")

            # Extract content based on model family
            content = None
            if model_family == "anthropic_messages":
                # Messages API returns content in a list, typically with one item
                if (
                    response_body.get("content")
                    and isinstance(response_body["content"], list)
                    and len(response_body["content"]) > 0
                ):
                    content_block = response_body["content"][0]
                    if content_block.get("type") == "text":
                        content = content_block.get("text")
            elif model_family == "meta":
                content = response_body.get("generation")
            elif model_family == "amazon_titan_text":
                results = response_body.get("results")
                if results and isinstance(results, list) and len(results) > 0:
                    content = results[0].get("outputText")
                else:
                    content = response_body.get("outputText")  # Fallback

            # Add elif blocks here for parsing other families

            if content is None:
                logger.warning(
                    f"Could not extract generated content from response for model {model}. Response body: {response_body}"
                )
                content = ""

            # Try to parse as JSON if structured output was requested
            final_response = content.strip()
            if structured_output_format:
                logger.info("Attempting to parse response as JSON due to structured_output_format request.")
                try:
                    final_response = json.loads(final_response)  # Try parsing the cleaned string
                    logger.info("Successfully parsed response as JSON.")
                except json.JSONDecodeError as json_err:
                    logger.warning(f"Failed to parse response as JSON: {json_err}. Returning raw string content.")
                    pass

            return {
                "response": final_response,
            }
        except Exception as e:
            logger.error(f"Unexpected error invoking Bedrock model '{model}': {e}", exc_info=True)
            raise Exception(f"Error invoking Bedrock model '{model}': {str(e)}") from e


if __name__ == "__main__":
    print("🧪 Testing BedrockProvider within Keep framework...")
    
    # Create provider instance  
    context_manager = ContextManager(tenant_id="test-tenant")
    
    # Create config with authentication
    auth_config = {
        "access_key": None,  # Uses SSO
        "secret_access_key": None,
        "region": "us-east-2"
    }
    config = ProviderConfig(authentication=auth_config)
    
    bedrock_provider = BedrockProvider(context_manager, "test-bedrock", config)
    
    try:
        print("BedrockProvider created successfully.")
        print("Using SSO authentication")
        print("Ready to test Bedrock queries.")
        
        #Test Query
        response = bedrock_provider._query(
        prompt="Give me a random fun fact.", 
        max_tokens=50
        )
        print(f"Response: {response['response']}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
