import json
import dataclasses
import pydantic
from anthropic import Anthropic

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AnthropicProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Anthropic API Key",
            "sensitive": True,
        },
    )


class AnthropicProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Anthropic Claude"
    PROVIDER_CATEGORY = ["AI"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AnthropicProviderAuthConfig(
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
        model="claude-3-sonnet-20240229",
        max_tokens=1024,
        structured_output_format=None,
    ):
        client = Anthropic(api_key=self.authentication_config.api_key)
        
        messages = [{"role": "user", "content": prompt}]
        
        # Handle structured output with system prompt if needed
        system_prompt = ""
        if structured_output_format:
            schema = structured_output_format.get("json_schema", {})
            system_prompt = (
                f"You must respond with valid JSON that matches this schema: {json.dumps(schema)}\n"
                "Your response must be parseable JSON and nothing else."
            )

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
            system=system_prompt if system_prompt else None
        )
        
        content = response.content[0].text
        
        try:
            content = json.loads(content)
        except Exception:
            pass

        return {
            "response": content,
        }


if __name__ == "__main__":
    import os
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    config = ProviderConfig(
        description="Claude Provider",
        authentication={
            "api_key": api_key,
        },
    )

    provider = AnthropicProvider(
        context_manager=context_manager,
        provider_id="claude_provider",
        config=config,
    )

    print(
        provider.query(
            prompt="Here is an alert, define environment for it: Clients are panicking, nothing works.",
            model="claude-3-sonnet-20240229",
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