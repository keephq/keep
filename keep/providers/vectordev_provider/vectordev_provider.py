import dataclasses
import json

import pydantic

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class VectordevProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "API key", "sensitive": True}
    )


class VectordevProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Vector"
    PROVIDER_CATEGORY = ["Monitoring", "Developer Tools"]
    PROVIDER_COMING_SOON = True

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = VectordevProviderAuthConfig(
            **self.config.authentication
        )

    def _format_alert(
        event: list[dict], provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        events = []
        # event is a list of events
        for e in event:
            event_json = None
            try:
                event_json = json.loads(e.get("message"))
            except json.JSONDecodeError:
                pass

            events.append(
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
        return events

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass
