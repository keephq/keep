"""
AxiomProvider is a class that allows to ingest/digest data from Axiom.
"""
import dataclasses
import datetime
from typing import Optional

import pydantic
import requests

from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class AxiomAuthConfig:
    """
    Axiom authentication configuration.
    """

    api_token: str
    organization_id: Optional[str]


class AxiomProvider(BaseProvider):
    """
    Axiom provider class.
    """

    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Axiom provider.

        """
        self.authentication_config = AxiomAuthConfig(**self.config.authentication)

    def query(self, **kwargs: dict):
        """
        Query Axiom using the given query

        Args:
            query (str): command to execute

        Returns:
            https://axiom.co/docs/restapi/query#response-example
        """
        datasets_api_url = kwargs.get("api_url", "https://api.axiom.co/v1/datasets")
        organization_id = kwargs.get(
            "organization_id", self.authentication_config.organization_id
        )
        if not organization_id:
            raise Exception("organization_id is required for Axiom provider")

        dataset = kwargs.get("dataset")
        if not dataset:
            raise Exception("dataset is required for Axiom provider")

        nocache = kwargs.get("nocache", "true")

        headers = {
            "Authorization": f"Bearer {self.authentication_config.api_token}",
            "X-Axiom-Org-ID": organization_id,
        }

        # Todo: support easier syntax (e.g. 1d, 1h, 1m, 1s, etc)
        startTime = kwargs.get("startTime", datetime.datetime.utcnow().isoformat())
        endTime = kwargs.get(
            "endTime", datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        body = {"startTime": startTime, "endTime": endTime}

        # Todo: add support for body parameters (https://axiom.co/docs/restapi/query#request-example)
        response = requests.post(
            f"{datasets_api_url}/{dataset}/query?nocache={nocache}",
            headers=headers,
            json=body,
        )

        # Todo: log response details for better error handling
        return response.json()


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    api_token = os.environ.get("AXIOM_API_TOKEN")

    config = {
        "authentication": {"api_token": api_token, "organization_id": "keephq-rxpb"},
    }
    provider = ProvidersFactory.get_provider(
        provider_id="axiom_test", provider_type="axiom", provider_config=config
    )
    result = provider.query(dataset="test", startTime="2023-04-26T09:52:04.000Z")
    print(result)
