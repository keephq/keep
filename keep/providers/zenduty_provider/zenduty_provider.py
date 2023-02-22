import dataclasses

import pydantic
import zenduty

from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ZendutyProviderAuthConfig:
    """Slack authentication configuration."""

    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Zenduty api key"}
    )


class ZendutyProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)
        self.zenduty_client = zenduty.IncidentsApi(
            zenduty.ApiClient(self.authentication_config.api_key)
        )

    def validate_config(self):
        self.authentication_config = ZendutyProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def notify(self, **kwargs: dict):
        """
        Create incident Zenduty using the Zenduty API

        https://github.com/Zenduty/zenduty-python-sdk

        Args:
            kwargs (dict): The providers with context
        """
        self.logger.debug("Notifying incident to Zenduty")
        title = kwargs.pop("title", "")
        summary = kwargs.pop("summary", "")
        user = kwargs.pop("user", None)
        service = kwargs.pop("service", "")
        policy = kwargs.pop("policy", "")

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
        resp = self.zenduty_client.create_incident(body)
        assert resp.status == 201
        self.logger.debug("Alert message notified to Zenduty")


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    zenduty_key = os.environ.get("ZENDUTY_KEY")
    assert zenduty_key

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="Zenduty Output Provider",
        authentication={"api_key": zenduty_key},
    )
    provider = ZendutyProvider(provider_id="zenduty-test", config=config)
    provider.notify(
        message="Simple incident showing context with name: {name}".format(
            name="John Doe"
        ),
        title="Simple incident",
        summary="Simple incident showing context with name: John Doe",
        service="9c6ddc88-16a0-4ce8-85ab-181760d8cb87",
    )
