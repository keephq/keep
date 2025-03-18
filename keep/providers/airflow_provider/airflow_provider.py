from datetime import datetime, timezone

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class AirflowProvider(BaseProvider):
    """Enrich alerts with data sent from Airflow."""

    PROVIDER_DISPLAY_NAME = "Airflow"
    PROVIDER_CATEGORY = ["Orchestration"]
    FINGERPRINT_FIELDS = ["fingerprint"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        pass

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        alert = AlertDto(
            id=event.get("fingerprint"),
            fingerprint=event.get("fingerprint"),
            name=event.get("name", "Airflow Alert"),
            message=event.get("message"),
            description=event.get("description"),
            severity=event.get("severity", "critical"),
            status=event.get("status", "firing"),
            environment=event.get("environment"),
            service=event.get("service"),
            source=["airflow"],
            url=event.get("url"),
            lastReceived=event.get(
                "lastReceived", datetime.now(tz=timezone.utc).isoformat()
            ),
            labels=event.get("labels", {}),
        )
        return alert
