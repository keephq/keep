import json
import dataclasses
import pydantic
import google.generativeai as genai

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GeminiProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Google AI API Key",
            "sensitive": True,
        },
    )


class GeminiProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Gemini"
    PROVIDER_CATEGORY = ["AI"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GeminiProviderAuthConfig(
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
        model="gemini-pro",
        max_tokens=1024,
        structured_output_format=None,
    ):
        genai.configure(api_key=self.authentication_config.api_key)
        
        model = genai.GenerativeModel(model)
        
        # Prepare system prompt for structured output if needed
        if structured_output_format:
            schema = structured_output_format.get("json_schema", {})
            prompt = (
                f"You must respond with valid JSON that matches this schema: {json.dumps(schema)}\n"
                f"Your response must be parseable JSON and nothing else.\n\n"
                f"User query: {prompt}"
            )

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
            ),
        )
        
        content = response.text
        
        # Try to parse as JSON if structured output was requested
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

    api_key = os.environ.get("GOOGLE_API_KEY")

    config = ProviderConfig(
        description="Gemini Provider",
        authentication={
            "api_key": api_key,
        },
    )

    provider = GeminiProvider(
        context_manager=context_manager,
        provider_id="gemini_provider",
        config=config,
    )

    print(
        provider.query(
            prompt="Here is an alert, define environment for it: Clients are panicking, nothing works.",
            model="gemini-pro",
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