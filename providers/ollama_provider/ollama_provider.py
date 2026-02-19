import json
import dataclasses
import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class OllamaProviderAuthConfig:
    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Ollama API Host URL",
            "sensitive": False,
        },
        default="http://localhost:11434",
    )


class OllamaProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Ollama"
    PROVIDER_CATEGORY = ["AI"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = OllamaProviderAuthConfig(
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
        model="llama3.1:8b-instruct-q6_K",
        max_tokens=1024,
        structured_output_format=None,
    ):
        # Build the API URL
        api_url = f"{self.authentication_config.host}/api/generate"

        # Prepare the request payload
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "raw": True,  # Raw mode for more consistent output
            "options": {
                "num_predict": max_tokens,
            },
        }

        if structured_output_format is not None:
            payload["format"] = structured_output_format

        try:
            # Make the API request
            response = requests.post(api_url, json=payload)
            response.raise_for_status()
            content = response.json()["response"]

            # Try to parse as JSON if structured output was requested
            if structured_output_format:
                try:
                    content = json.loads(content)
                except Exception:
                    pass

            return {
                "response": content,
            }

        except requests.exceptions.RequestException as e:
            raise Exception(f"Error calling Ollama API: {str(e)}")


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        description="Ollama Provider",
        authentication={
            "host": "http://localhost:11434",  # Default Ollama host
        },
    )

    provider = OllamaProvider(
        context_manager=context_manager,
        provider_id="ollama_provider",
        config=config,
    )

    print(
        provider.query(
            prompt="Here is an alert, define environment for it: Clients are panicking, nothing works.",
            model="llama3.1:8b-instruct-q6_K",  # or any other model you have pulled in Ollama
            structured_output_format={
                "type": "object",
                "properties": {
                    "environment": {
                        "type": "string",
                        "enum": ['production', 'debug']
                    },
                },
                "required": ["environment"],
            },
            max_tokens=100,
        )
    )
