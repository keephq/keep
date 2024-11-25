import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ZendutyProviderAuthConfig:
    """Zenduty authentication configuration."""

    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Zenduty api key", "sensitive": True}
    )


class ZendutyProvider(BaseProvider):
    """Create incident in Zenduty."""

    PROVIDER_DISPLAY_NAME = "Zenduty"
    PROVIDER_CATEGORY = ["Incident Management"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ZendutyProviderAuthConfig(
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
        summary: str = "",
        service: str = "",
        user: str = "",
        policy: str = "",
        **kwargs: dict
    ):
        """
        Create incident Zenduty using the Zenduty API

        https://github.com/Zenduty/zenduty-python-sdk

        Args:
            kwargs (dict): The providers with context
        """
        self.logger.debug("Notifying incident to Zenduty")

        if not service:
            raise ProviderException("Service is required")
        if not title or not summary:
            raise ProviderException("Title and summary are required")

        body = {
            "service": service,
            "policy": policy,
            "user": user,
            "title": title,
            "summary": summary,
        }
        # https://github.com/Zenduty/zenduty-python-sdk/blob/master/zenduty/api_client.py#L11
        headers = {
            "Authorization": "Token " + self.authentication_config.api_key,
        }
        resp = requests.post(
            url="https://www.zenduty.com/api/incidents/", json=body, headers=headers
        )
        assert resp.status == 201
        self.logger.debug("Alert message notified to Zenduty")


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    zenduty_key = os.environ.get("ZENDUTY_KEY")
    assert zenduty_key

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="Zenduty Output Provider",
        authentication={"api_key": zenduty_key},
    )
    provider = ZendutyProvider(
        context_manager, provider_id="zenduty-test", config=config
    )
    provider.notify(
        message="Simple incident showing context with name: John Doe",
        title="Simple incident",
        summary="Simple incident showing context with name: John Doe",
        service="9c6ddc88-16a0-4ce8-85ab-181760d8cb87",
    )
