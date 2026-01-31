import dataclasses
import requests
import pydantic
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    url: str = dataclasses.field(metadata={"required": True, "description": "Nagios Instance URL"})
    api_key: str = dataclasses.field(metadata={"required": True, "description": "Nagios API Key", "sensitive": True})

class NagiosProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_CATEGORY = ["Monitoring"]

    def __init__(self, context_manager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = NagiosProviderAuthConfig(**self.config.authentication)

    def _get_alerts(self, **kwargs):
        # Fetch status from Nagios XI API
        endpoint = f"{self.authentication_config.url}/nagiosxi/api/v1/objects/hoststatus"
        params = {"apikey": self.authentication_config.api_key}
        response = requests.get(endpoint, params=params, verify=False)
        response.raise_for_status()
        return response.json().get("hoststatus", [])

print("Nagios Provider implemented.")
