"""
SentryProvider is a class that provides a way to read data from Sentry.
"""
import requests

from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


class SentryProvider(BaseProvider):
    def __init__(self, config: ProviderConfig, **kwargs):
        self.sentry_project = kwargs.get("project")
        super().__init__(config)
        self.sentry_org_slug = self.config.authentication.get("org_slug")
        # Use the 'discover' web API to get the list of events
        query_param = f'project%3A{kwargs.get("project")}'
        date_param = "14d" or kwargs.get("time")
        self.sentry_events_url = f"https://{self.sentry_org_slug}.sentry.io/api/0/organizations/{self.sentry_org_slug}/events/?field=title&field=event.type&field=project&field=user.display&field=timestamp&field=replayId&per_page=50 \
                                  &query={query_param}&referrer=api.discover.query-table&sort=-timestamp&statsPeriod={date_param}"

    def dispose(self):
        return

    def validate_config(self):
        """
        Validates required configuration for Sentry's provider.

        Raises:
            ProviderConfigException: dsn or token is missing in authentication.
        """
        if "api_token" not in self.config.authentication:
            raise ProviderConfigException("missing token in authentication")

        if "org_slug" not in self.config.authentication:
            raise ProviderConfigException("missing org slug in authentication")

        if not self.sentry_project:
            raise ProviderConfigException("missing project in configuration")

    def query(self, query: str, **kwargs: dict):
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
        params = {"limit": 100}
        response = requests.get(self.sentry_events_url, headers=headers, params=params)
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
        provider_type="sentry", provider_config=config, project=sentry_project
    )
    result = provider.query("")
    print(result)
