import dataclasses
import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class FlashdutyProviderAuthConfig:
    """Flashduty authentication configuration."""

    integration_key: str = dataclasses.field(
        metadata= {
            "required": True,
            "description": "Flashduty integration key",
            "sensitive": True,
        }
    )


class FlashdutyProvider(BaseProvider):
    """Create incident in Flashduty."""

    PROVIDER_DISPLAY_NAME = "Flashduty"
    PROVIDER_CATEGORY = ["Incident Management"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FlashdutyProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(
        self,
        title: str = "",
        event_status: str = "",
        description: str = "",
        alert_key: str = "",
        labels: dict = {}
    ):
        """
        Create incident Flashduty using the Flashduty API

        https://docs.flashcat.cloud/en/flashduty/custom-alert-integration-guide?nav=01JCQ7A4N4WRWNXW8EWEHXCMF5

        Args:
            title (str): The title of the incident
            event_status (str): The status of the incident, one of: Info, Warning, Critical, Ok
            description (str): The description of the incident
            alert_key (str): Alert identifier, used to update or automatically recover existing alerts. If you're reporting a recovery event, this value must exist.
            labels (dict): The labels of the incident
        """

        self.logger.debug("Notifying incident to Flashduty")
        if not title:
            raise ProviderException("Title is required")
        if not event_status:
            raise ProviderException("Event status is required")

        body = {
            "title": title,
            "event_status": event_status,
            "description": description,
            "alert_key": alert_key,
            "labels": labels,
        }

        headers = {
            "Content-Type": "application/json",
        }
        resp = requests.post(
            url=f"https://api.flashcat.cloud/event/push/alert/standard?integration_key={self.authentication_config.integration_key}", json=body, headers=headers
        )
        assert resp.status_code == 200
        self.logger.debug("Alert message notified to Flashduty")


if __name__ == "__main__":
    # Output test messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    integration_key = os.environ.get("INTEGRATION_KEY")
    assert integration_key

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="Flashduty Output Provider",
        authentication={"integration_key": integration_key},
    )
    provider = FlashdutyProvider(
        context_manager, provider_id="flashduty-test", config=config
    )
    provider.notify(
        title="Test incident",
        event_status="Info",
        description="Test description",
        alert_key="1234567890",
        labels={"service": "10.10.10.10"},
    )

