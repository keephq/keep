import json
import dataclasses
import pydantic

from openai import OpenAI

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class HuggingFaceProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "HuggingFace API Key",
            "sensitive": True,
        },
    )
    endpoint_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "HuggingFace Inference Endpoint URL",
            "sensitive": False,
        },
    )


class HuggingFaceProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "HuggingFace"
    PROVIDER_CATEGORY = ["AI"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = HuggingFaceProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {}
        return scopes

    def _query(
        self,
        prompt,
        model=None,  # Not used since the model is specified in the endpoint URL
        max_tokens=1024,
        structured_output_format=None,
    ):
        """
        Query the HuggingFace Inference Endpoint with the given prompt.
        Args:
            prompt (str): The prompt to query the model with.
            model (str, optional): Not used, as the model is determined by the endpoint.
            max_tokens (int): The maximum number of tokens to generate.
            structured_output_format (dict): The format for structured output.
        """
        # Create an OpenAI client instance configured to use the HuggingFace endpoint
        client = OpenAI(
            api_key=self.authentication_config.api_key,
            base_url=self.authentication_config.endpoint_url,
        )

        # Prepare the request payload
        messages = [{"role": "user", "content": prompt}]
        
        # Make the API request using the OpenAI client
        try:
            response = client.chat.completions.create(
                model=model if model else "default",  # 'model' param is required but will be ignored by HF
                messages=messages,
                max_tokens=max_tokens,
                response_format=structured_output_format,
            )
            
            # Extract the response content
            content = response.choices[0].message.content
            
            # Try to parse as JSON if it looks like JSON
            try:
                content = json.loads(content)
            except Exception:
                pass
                
            return {
                "response": content,
            }
            
        except Exception as e:
            # Handle any errors that might occur during the API call
            raise Exception(f"Error calling HuggingFace Inference API: {str(e)}")


if __name__ == "__main__":
    import os
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_key = os.environ.get("HUGGINGFACE_API_KEY")
    endpoint_url = os.environ.get("HUGGINGFACE_ENDPOINT_URL")

    config = ProviderConfig(
        description="HuggingFace Inference Provider",
        authentication={
            "api_key": api_key,
            "endpoint_url": endpoint_url,
        },
    )

    provider = HuggingFaceProvider(
        context_manager=context_manager,
        provider_id="huggingface_provider",
        config=config,
    )

    print(
        provider.query(
            prompt="Here is an alert, define environment for it: Clients are panicking, nothing works.",
            structured_output_format={
                "type": "json_object",
                "schema": {
                    "type": "object",
                    "properties": {
                        "environment": {
                            "type": "string",
                            "enum": ["production", "debug", "pre-prod"],
                        },
                    },
                    "required": ["environment"],
                },
            },
            max_tokens=100,
        )
    )