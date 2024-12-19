import dataclasses

import random
import json

import pydantic
import logging

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.api.models.alert import AlertDto
from keep.providers.providers_factory import ProvidersFactory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pydantic.dataclasses.dataclass
class VectordevProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "API key", "sensitive": True}
    )


class VectordevProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Vector"
    PROVIDER_CATEGORY = ["Monitoring", "Developer Tools"]
    PROVIDER_COMING_SOON = True

    # Mapping from vector sources to keep providers
    SOURCE_TO_PROVIDER_MAP = {
        "prometheus": "prometheus",
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = VectordevProviderAuthConfig(
            **self.config.authentication
        )

    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        events = []
        if isinstance(event, list):
            events = event
        else:
            events = [event]
        alert_dtos = []
        for event in events:
            if "keep_source_type" in event and event["keep_source_type"] in VectordevProvider.SOURCE_TO_PROVIDER_MAP:
                provider_class = ProvidersFactory.get_provider_class(VectordevProvider.SOURCE_TO_PROVIDER_MAP[event["keep_source_type"])
                alert_dtos.extend(provider_class._format_alert(event["message"],provider_instance))
            else:
                message_str = json.dumps(e.get("message"))
                alert_dtos.append(
                AlertDto(
                    name="",
                    message=message_str,
                    description=message_str,
                    lastReceived=e.get("timestamp"),
                    source_type=e.get("source_type"),
                    source=["vectordev"],
                    original_event=e.get("message"),
                )
            )
        return alert_dtos

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    @classmethod
    def simulate_alert(cls, **kwargs) -> dict:
        provider = random.choice(list(VectordevProvider.SOURCE_TO_PROVIDER_MAP.values()))
        provider_class = ProvidersFactory.get_provider_class(provider)
        return provider_class.simulate_alert(to_wrap_with_provider_type=True)

