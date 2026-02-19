import json
import dataclasses
import pydantic
import requests

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
        temperature=0.7,
        structured_output_format=None,
    ):
        """
        Query the DeepSeek API with the given prompt and model.
        Args:
            prompt (str): The prompt to query the model with.
            model (str): The model to query.
            max_tokens (int): The maximum number of tokens to generate.
            temperature (float): The temperature to use for generation.
            structured_output_format (dict): The structured output format to use.
        """
        api_url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.authentication_config.api_key}",
        }

        messages = [{"role": "user", "content": prompt}]

        # Handle structured output with system prompt if needed
        # Note: DeepSeek supports JSON mode if explicitly asked or through system prompt
        if structured_output_format:
            schema = structured_output_format.get("json_schema", {})
            system_prompt = (
                f"You must respond with valid JSON that matches this schema: {json.dumps(schema)}\n"
                "Your response must be parseable JSON and nothing else."
            )
            messages.insert(0, {"role": "system", "content": system_prompt})

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if structured_output_format:
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]

        if structured_output_format:
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

    print(
        provider.query(
            prompt="Tell me a joke about DevOps.",
            model="deepseek-chat",
            max_tokens=100,
        )
    )
