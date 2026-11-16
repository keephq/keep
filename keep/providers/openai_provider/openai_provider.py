import dataclasses
import json
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
            "description": "OpenAI API Key",
            "sensitive": True,
        },
    )
    organization: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "OpenAI Organization ID",
            "sensitive": True,
        },
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
        model="gpt-4o-mini",
        max_tokens=1024,
        structured_output_format=None,
    ):
        """
        Query the OpenAI API with the given prompt.
        Args:
            prompt (str): The user query.
            model (str): The model to use for the query.
            max_tokens (int): The maximum number of tokens to generate.
            structured_output_format (dict): The structured output format.
        """
        try:
            max_tokens = int(max_tokens)
        except (TypeError, ValueError):
            max_tokens = 1024

        client = OpenAI(
            api_key=self.authentication_config.api_key,
            organization=self.authentication_config.organization,
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            response_format=structured_output_format,
        )

        if not response.choices:
            self.logger.warning("OpenAI returned an empty choices list.")
            return {"response": ""}

        response = response.choices[0].message.content
        try:
            response = json.loads(response)
        except Exception:
            pass

        return {
            "response": response,
        }


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_key = os.environ.get("OPENAI_API_KEY")

    config = ProviderConfig(
        description="OpenAI Provider",
        authentication={
            "api_key": api_key,
        },
    )

    provider = OpenaiProvider(
        context_manager=context_manager,
        provider_id="openai_provider",
        config=config,
    )

    print(
        provider.query(
            prompt="Which is the highest mountain in the world?",
            model="gpt-4o-mini",
        )
    )