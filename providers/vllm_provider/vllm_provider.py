import json
import dataclasses
import pydantic
import requests
from typing import Optional, Dict, Any

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class VllmProviderAuthConfig:
    api_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "vLLM API endpoint URL",
            "sensitive": False,
        }
    )
    api_key: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Optional API key if your vLLM deployment requires authentication",
            "sensitive": True,
        },
        default=None,
    )


class VllmProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "vLLM"
    PROVIDER_CATEGORY = ["AI"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = VllmProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {}
        return scopes

    def _prepare_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.authentication_config.api_key:
            headers["Authorization"] = f"Bearer {self.authentication_config.api_key}"
        return headers

    def _format_messages(self, prompt: str) -> str:
        """Format the prompt in a chat-style format if needed."""
        # You might want to customize this based on your model's requirements
        return prompt

    def _query(
        self,
        prompt: str,
        temperature: float = 0.7,
        model: str = "Qwen/Qwen1.5-1.8B-Chat",
        max_tokens: int = 1024,
        structured_output_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        headers = self._prepare_headers()
        formatted_prompt = self._format_messages(prompt)

        # Prepare the request payload
        payload = {
            "model": model,
            "prompt": formatted_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Add structured output format if provided
        if structured_output_format:
            payload["guided_json"] = structured_output_format

        try:
            response = requests.post(
                self.authentication_config.api_url + "/v1/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            
            # Parse the response
            result = response.json()
            
            # Extract the generated text from the response

            # Adjust this based on your vLLM API response structure
            try:
                generated_text = result["choices"][0]['text']
            except KeyError:
                generated_text = ""
            
            # Try to parse as JSON if it's meant to be structured
            if structured_output_format:
                try:
                    generated_text = json.loads(generated_text)
                except json.JSONDecodeError:
                    raise ProviderException(
                        f"Failed to parse generated text as JSON: {generated_text}. Model not following the structured output format. Response: {result}"
                    )

            return {
                "response": generated_text,
            }

        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Error querying vLLM API: {str(e)}")


if __name__ == "__main__":
    import os
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        description="vLLM Provider",
        authentication={
            "api_url": "http://localhost:8000/v1/completions",  # Default vLLM API endpoint
            "api_key": os.environ.get("VLLM_API_KEY"),  # Optional
        },
    )

    provider = VllmProvider(
        context_manager=context_manager,
        provider_id="vllm_provider",
        config=config,
    )

    print(
        provider.query(
            prompt="Here is an alert, define environment for it: Clients are panicking, nothing works.",
            temperature=0,
            model="Qwen/Qwen1.5-1.8B-Chat",
            structured_output_format={
                "type": "object",
                "properties": {
                    "environment": {
                        "type": "string",
                        "enum": ["production", "debug", "pre-prod"],
                    },
                },
                "required": ["environment"],
            },
            max_tokens=100,
        )
    )
