import dataclasses

import random
import json

import pydantic

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.api.models.alert import AlertDto
from keep.providers.providers_factory import ProvidersFactory


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
        "grafana": "grafana",
    }

    # Mapping from vector sources to keep providers
    SOURCE_TO_PROVIDER_MAP = {
        "prometheus": "prometheus",
        "grafana": "grafana",
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
        try:
            event_type = event["source_type"]
            provider_class = ProvidersFactory.get_provider_class(VectordevProvider.SOURCE_TO_PROVIDER_MAP[event_type])
            return provider_class._format_alert(event["event"],provider_instance)
        except Exception as e:
            alert_dtos = []
            if isinstance(event, list):
                return event
            else:
                alerts = event.get("alerts", [event])
            for e in event:
                event_json = None
                try:
                    event_json = json.loads(e.get("message"))
                except json.JSONDecodeError:
                    pass
                alert_dtos.append(
                AlertDto(
                    name="",
                    host=e.get("host"),
                    message=e.get("message"),
                    description=e.get("message"),
                    lastReceived=e.get("timestamp"),
                    source_type=e.get("source_type"),
                    source=["vectordev"],
                    original_event=event_json,
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

