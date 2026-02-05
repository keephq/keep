import dataclasses
import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class LlamacppProviderAuthConfig:
    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Llama.cpp Server Host URL",
            "sensitive": False,
        },
        default="http://localhost:8080"
    )


class LlamacppProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Llama.cpp"
    PROVIDER_CATEGORY = ["AI"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LlamacppProviderAuthConfig(
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
        max_tokens=1024,
    ):
        # Build the API URL for completion
        api_url = f"{self.authentication_config.host}/completion"

        # Prepare the request payload
        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": 0.7,
            "stop": ["\n\n"],  # Common stop sequence
            "stream": False
        }

        try:
            # Make the API request
            response = requests.post(api_url, json=payload)
            response.raise_for_status()
            content = response.json()["content"]
            
            return {
                "response": content,
            }

        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Error calling Llama.cpp API: {str(e)}")


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        description="Llama.cpp Provider",
        authentication={
            "host": "http://localhost:8080",  # Default Llama.cpp server host
        },
    )

    provider = LlamacppProvider(
        context_manager=context_manager,
        provider_id="llamacpp_provider",
        config=config,
    )

    print(
        provider.query(
            prompt="Here is an alert, define environment for it: Clients are panicking, nothing works. Give one word: production or dev.",
            max_tokens=10,
        )
    )