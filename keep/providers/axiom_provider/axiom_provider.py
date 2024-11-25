"""
AxiomProvider is a class that allows to ingest/digest data from Axiom.
"""

import dataclasses
from typing import Optional

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class AxiomProviderAuthConfig:
    """
    Axiom authentication configuration.
    """

    api_token: str = dataclasses.field(
        metadata={"required": True, "sensitive": True, "description": "Axiom API Token"}
    )
    organization_id: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "sensitive": False,
            "description": "Axiom Organization ID",
        },
        default=None,
    )


class AxiomProvider(BaseProvider):
    """Enrich alerts with data from Axiom."""

    PROVIDER_DISPLAY_NAME = "Axiom"
    PROVIDER_CATEGORY = ["Monitoring"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Axiom provider.

        """
        self.authentication_config = AxiomProviderAuthConfig(
            **self.config.authentication
        )

    def _query(
        self,
        dataset=None,
        datasets_api_url=None,
        organization_id=None,
        startTime=None,
        endTime=None,
        **kwargs: dict,
    ):
        """
        Query Axiom using the given query

        Args:
            query (str): command to execute

        Returns:
            https://axiom.co/docs/restapi/query#response-example
        """
        datasets_api_url = datasets_api_url or kwargs.get(
            "api_url", "https://api.axiom.co/v1/datasets"
        )
        organization_id = organization_id or self.authentication_config.organization_id
        if not organization_id:
            raise Exception("organization_id is required for Axiom provider")

        if not dataset:
            raise Exception("dataset is required for Axiom provider")

        nocache = kwargs.get("nocache", "true")

        headers = {
            "Authorization": f"Bearer {self.authentication_config.api_token}",
            "X-Axiom-Org-ID": organization_id,
        }

        # Todo: support easier syntax (e.g. 1d, 1h, 1m, 1s, etc)
        body = {"startTime": startTime, "endTime": endTime}

        # Todo: add support for body parameters (https://axiom.co/docs/restapi/query#request-example)
        response = requests.post(
            f"{datasets_api_url}/{dataset}/query?nocache={nocache}?format=tabular",
            headers=headers,
            json=body,
        )

        # Todo: log response details for better error handling
        return response.json()


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

    api_token = os.environ.get("AXIOM_API_TOKEN")

    config = {
        "authentication": {"api_token": api_token, "organization_id": "keephq-rxpb"},
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="axiom_test",
        provider_type="axiom",
        provider_config=config,
    )
    result = provider.query(dataset="test", startTime="2023-04-26T09:52:04.000Z")
    print(result)
