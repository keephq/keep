import json
import dataclasses
import pydantic
import requests
from typing import Optional, Dict, Any, List

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class LitellmProviderAuthConfig:
    api_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "LiteLLM API endpoint URL",
            "sensitive": False,
        }
    )
    api_key: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Optional API key if your LiteLLM deployment requires authentication",
            "sensitive": True,
        },
        default=None,
    )


class LitellmProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "LiteLLM"
    PROVIDER_CATEGORY = ["AI"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LitellmProviderAuthConfig(
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

    def _format_messages(self, prompt: str) -> List[Dict[str, str]]:
        """Format the prompt as a chat message."""
        return [{"role": "user", "content": prompt}]

    def _query(
        self,
        prompt: str,
        temperature: float = 0.7,
        model: str = "gpt-3.5-turbo",
        max_tokens: int = 1024,
        structured_output_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        headers = self._prepare_headers()
        formatted_messages = self._format_messages(prompt)

        # Prepare the request payload
        payload = {
            "model": model,
            "messages": formatted_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Add structured output format if provided
        if structured_output_format:
            # Append system message with format instructions
            format_instructions = f"You must respond with a JSON object that conforms to the following schema: {json.dumps(structured_output_format)}"
            payload["messages"].insert(
                0, {"role": "system", "content": format_instructions}
            )

        try:
            response = requests.post(
                f"{self.authentication_config.api_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()

            # Parse the response
            result = response.json()

            # Extract the generated text from the response
            try:
                generated_text = result["choices"][0]["message"]["content"]
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
            raise ProviderException(f"Error querying LiteLLM API: {str(e)}")


if __name__ == "__main__":
    import os
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        description="LiteLLM Provider",
        authentication={
            "api_url": "http://localhost:4000",  # Default LiteLLM API endpoint
            "api_key": os.environ.get("LITELLM_API_KEY"),  # Optional
        },
    )

    provider = LitellmProvider(
        context_manager=context_manager,
        provider_id="litellm_provider",
        config=config,
    )

    print(
        provider.query(
            prompt="Here is an alert, define environment for it: Clients are panicking, nothing works.",
            temperature=0,
            model="gpt-3.5-turbo",
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
