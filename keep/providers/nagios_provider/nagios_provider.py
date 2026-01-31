import dataclasses
import requests
import pydantic
import logging
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    url: str = dataclasses.field(metadata={"required": True, "description": "Nagios Instance URL"})
    api_key: str = dataclasses.field(metadata={"required": True, "description": "Nagios API Key", "sensitive": True})
    verify_ssl: bool = dataclasses.field(default=True, metadata={"description": "Verify SSL certificate"})

class NagiosProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_CATEGORY = ["Monitoring"]

    def __init__(self, context_manager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = NagiosProviderAuthConfig(**self.config.authentication)

    def _get_alerts(self, **kwargs):
        endpoint = f"{self.authentication_config.url.rstrip('/')}/nagiosxi/api/v1/objects/hoststatus"
        params = {"apikey": self.authentication_config.api_key}
        # 加固点：显式超时设置 (防止挂起) 和 配置化SSL验证 (合规)
        try:
            response = requests.get(
                endpoint, 
                params=params, 
                verify=self.authentication_config.verify_ssl,
                timeout=30
            )
            response.raise_for_status()
            return response.json().get("hoststatus", [])
        except Exception as e:
            self.logger.error(f"Error fetching status from Nagios: {e}")
            return []

print("Keep HQ Provider: Nagios implementation HARDENED.")
