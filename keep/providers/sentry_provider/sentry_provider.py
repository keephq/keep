"""
SentryProvider is a class that provides a way to read data from Sentry.
"""
import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class SentryProviderAuthConfig:
    """Sentry authentication configuration."""

    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Sentry Api Key", "sensitive": True}
    )
    org_slug: str = dataclasses.field(
        metadata={"required": True, "description": "Sentry organization slug"}
    )


class SentryProvider(BaseProvider):
    """Enrich alerts with data from Sentry."""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.sentry_org_slug = self.config.authentication.get("org_slug")

    def get_events_url(self, project, date="14d"):
        return f"https://{self.sentry_org_slug}.sentry.io/api/0/organizations/{self.sentry_org_slug}/events/?field=title&field=event.type&field=project&field=user.display&field=timestamp&field=replayId&per_page=50 \
                                  &query={project}&referrer=api.discover.query-table&sort=-timestamp&statsPeriod={date}"

    def dispose(self):
        return

    def validate_config(self):
        """Validates required configuration for Sentry's provider."""
        self.authentication_config = SentryProviderAuthConfig(
            **self.config.authentication
        )

    def _query(self, query: str, **kwargs: dict):
        """
        Query Sentry using the given query

        Args:
            query (str): query to execute

        Returns:
            list[tuple] | list[dict]: results of the query
        """
        headers = {
            "Authorization": f"Bearer {self.config.authentication['api_token']}",
        }
        time = kwargs.get("time", "14d")
        project = kwargs.get("project")

        params = {"limit": 100}
        response = requests.get(
            self.get_events_url(project, time), headers=headers, params=params
        )
        response.raise_for_status()

        events = response.json()
        return events.get("data")  # returns a list of events

    def get_template(self):
        pass

    def get_parameters(self):
        return {}


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

    sentry_api_token = os.environ.get("SENTRY_API_TOKEN")
    sentry_org_slug = os.environ.get("SENTRY_ORG_SLUG")
    sentry_project = "python"

    config = {
        "id": "sentry-prod",
        "authentication": {"api_token": sentry_api_token, "org_slug": sentry_org_slug},
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_type="sentry",
        provider_config=config,
        project=sentry_project,
    )
    result = provider.query("")
    print(result)
