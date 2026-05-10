import json
import dataclasses
import pydantic
from anthropic import Anthropic, AuthenticationError

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
            "hint": "sk-ant-...",
        },
    )

    model: str = dataclasses.field(
        default="claude-sonnet-4-6",
        metadata={
            "required": False,
            "description": "Claude model to use",
            "type": "select",
            "options": [
                "claude-opus-4-5",
                "claude-sonnet-4-6",
                "claude-haiku-4-5-20251001",
            ],
        },
    )

    system_prompt: str = dataclasses.field(
        default="You are an expert SRE and security analyst. Analyze alerts and provide concise, actionable insights.",
        metadata={
            "required": False,
            "description": "System prompt that sets Claude's role for all requests in this provider.",
        },
    )


class AnthropicProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Anthropic"
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
        try:
            client = Anthropic(api_key=self.authentication_config.api_key)
            client.messages.create(
                model=self.authentication_config.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return {"api_key_valid": True}
        except AuthenticationError:
            return {"api_key_valid": "Invalid API key — check your Anthropic console."}
        except Exception as e:
            return {"api_key_valid": str(e)}

    def _query(
        self,
        prompt,
        model=None,
        max_tokens=1024,
        system_prompt=None,
        structured_output_format=None,
    ):
        """
        Query the Anthropic API with the given prompt and model.
        Args:
            prompt (str): The prompt to query the model with.
            model (str): The model to query (overrides provider config).
            max_tokens (int): The maximum number of tokens to generate.
            system_prompt (str): System prompt override for this call.
            structured_output_format (dict): The structured output format to use.
        """
      client = Anthropic(api_key=self.authentication_config.api_key)

        messages = [{"role": "user", "content": prompt}]

        # Resolve system prompt: call-level override > structured output schema > provider config
        resolved_system = system_prompt or self.authentication_config.system_prompt
        if structured_output_format:
            schema = structured_output_format.get("json_schema", {})
            resolved_system = (
                f"You must respond with valid JSON that matches this schema: {json.dumps(schema)}\n"
                "Your response must be parseable JSON and nothing else."
            )

        response = client.messages.create(
            model=model or self.authentication_config.model,
            max_tokens=max_tokens,
            messages=messages,
            system=resolved_system,
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
