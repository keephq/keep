import json
import dataclasses
import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GrokProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "X.AI Grok API Key",
            "sensitive": True,
        },
    )


class GrokProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Grok"
    PROVIDER_CATEGORY = ["AI"]
    API_BASE = "https://api.x.ai/v1"  # Example API base URL

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GrokProviderAuthConfig(
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
        model="grok-1",
        max_tokens=1024,
        structured_output_format=None,
    ):
        headers = {
            "Authorization": f"Bearer {self.authentication_config.api_key}",
            "Content-Type": "application/json"
        }

        # Prepare payload with structured output if needed
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }

        if structured_output_format:
            payload["response_format"] = structured_output_format

        try:
            response = requests.post(
                f"{self.API_BASE}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]

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
            raise ProviderException(f"Error calling Grok API: {str(e)}")


if __name__ == "__main__":
    import os
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_key = os.environ.get("GROK_API_KEY")

    config = ProviderConfig(
        description="Grok Provider",
        authentication={
            "api_key": api_key,
        },
    )

    provider = GrokProvider(
        context_manager=context_manager,
        provider_id="grok_provider",
        config=config,
    )

    print(
        provider.query(
            prompt="Here is an alert, define environment for it: Clients are panicking, nothing works.",
            model="grok-1",
            structured_output_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "environment_restoration",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "environment": {
                                "type": "string",
                                "enum": ["production", "debug", "pre-prod"],
                            },
                        },
                        "required": ["environment"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
            max_tokens=100,
        )
    )