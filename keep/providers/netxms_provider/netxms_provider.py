import dataclasses

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class NetxmsProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "NetXMS API key", "sensitive": True}
    )


class NetxmsProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "NetXMS"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_COMING_SOON = True

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = NetxmsProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass
