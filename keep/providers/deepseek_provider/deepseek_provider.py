import json
import dataclasses
import pydantic

from openai import OpenAI

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DeepseekProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "DeepSeek API Key",
            "sensitive": True,
        },
    )


class DeepseekProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "DeepSeek"
    PROVIDER_CATEGORY = ["AI"]
    BASE_URL = "https://api.deepseek.com"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DeepseekProviderAuthConfig(
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
        model="deepseek-chat",
        max_tokens=1024,
        system_prompt=None,
        structured_output_format=None,
    ):
        client = OpenAI(
            api_key=self.authentication_config.api_key,
            base_url=self.BASE_URL,
        )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
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

    api_key = os.environ.get("DEEPSEEK_API_KEY")

    config = ProviderConfig(
        description="DeepSeek Provider",
        authentication={
            "api_key": api_key,
        },
    )

    provider = DeepseekProvider(
        context_manager=context_manager,
        provider_id="deepseek_provider",
        config=config,
    )

    # Example usage with system prompt
    print(
        provider.query(
            prompt="Which is the longest river in the world? The Nile River.",
            model="deepseek-chat",
            system_prompt="""
            The user will provide some exam text. Please parse the "question" and "answer" 
            and output them in JSON format.

            EXAMPLE INPUT:
            Which is the highest mountain in the world? Mount Everest.

            EXAMPLE JSON OUTPUT:
            {
                "question": "Which is the highest mountain in the world?",
                "answer": "Mount Everest"
            }
            """,
            structured_output_format={
                "type": "json_object"
            },
            max_tokens=100,
        )
    )