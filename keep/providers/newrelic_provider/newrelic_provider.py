"""
NewrelicProvider is a provider that provides a way to interact with New Relic.
"""

import dataclasses

import pydantic
import requests

from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class NewrelicProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "New Relic API key",
            "sensitive": True,
        }
    )
    account_id: str = dataclasses.field(
        metadata={"required": True, "description": "New Relic account ID"}
    )


class NewrelicProvider(BaseProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)

    def dispose(self):
        """
        Nothing to dispose here
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for New-Relic provider.

        Raises:
            ProviderConfigException: user or account is missing in authentication.
            ProviderConfigException: private key
        """
        self.newrelic_config = NewrelicProviderAuthConfig(**self.config.authentication)

    def _query(self, **kwargs: dict):
        """
        Query New Relic account using the given NRQL

        Args:
            query (str): query to execute

        Returns:
            list[tuple] | list[dict]: results of the query
        """
        if not kwargs.get("nrql"):
            raise ProviderConfigException(
                "Missing NRQL query", provider_id=self.provider_id
            )

        new_relic_api = kwargs.get("new_relic_api", "https://api.newrelic.com/graphql")

        query = '{actor {account(id: %s) {nrql(query: "%s") {results}}}}'.format(
            self.newrelic_config.account_id, kwargs.get("nrql")
        )
        payload = {"query": query}

        response = requests.post(
            new_relic_api,
            headers={"Api-Key": self.newrelic_config.api_key},
            json=payload,
        )
        if not response.ok:
            self.logger.debug(
                "Failed to query New Relic",
                extra={"response": response.text, "query": query},
            )
            raise ProviderException(f"Failed to query New Relic: {response.text}")
        # results are in response.json()['data']['actor']['account']['nrql']['results'], should we return this?
        return response.json()
