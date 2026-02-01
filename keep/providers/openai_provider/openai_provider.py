import json
import dataclasses
import pydantic

from openai import OpenAI

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class OpenaiProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "OpenAI Platform API Key",
            "sensitive": True,
        },
    )
    organization_id: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "OpenAI Platform Organization ID",
            "sensitive": False,
        },
        default=None,
    )


class OpenaiProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "OpenAI"
    PROVIDER_CATEGORY = ["AI"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = OpenaiProviderAuthConfig(
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
        model="gpt-3.5-turbo",
        max_tokens=1024,
        structured_output_format=None,
    ):
        client = OpenAI(
            api_key=self.authentication_config.api_key,
            organization=self.authentication_config.organization_id,
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            response_format=structured_output_format,
        )
        response = response.choices[0].message.content
        try:
            response = json.loads(response)
        except Exception:
            pass

        return {
            "response": response,
        }


if __name__ == "__main__":
    import os
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_key = os.environ.get("API_KEY")

    config = ProviderConfig(
        description="My Provider",
        authentication={
            "api_key": api_key,
        },
    )

    provider = OpenaiProvider(
        context_manager=context_manager,
        provider_id="my_provider",
        config=config,
    )

    print(
        provider.query(
            prompt="Here is an alert, define environment for it: Clients are panicking, nothing works.",
            model="gpt-4o-mini",
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

    # https://platform.openai.com/docs/guides/function-calling
