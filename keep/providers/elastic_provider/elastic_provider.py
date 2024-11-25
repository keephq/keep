"""
Elasticsearch provider.
"""

import dataclasses
import json

import pydantic
from elasticsearch import Elasticsearch

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.exceptions.provider_connection_failed import ProviderConnectionFailed
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class ElasticProviderAuthConfig:
    """Elasticsearch authentication configuration."""

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Elasticsearch Api Key",
            "sensitive": True,
        }
    )
    host: str = dataclasses.field(
        default="", metadata={"required": False, "description": "Elasticsearch host"}
    )
    cloud_id: str = dataclasses.field(
        default="",
        metadata={"required": False, "description": "Elasticsearch cloud id"},
    )

    @pydantic.root_validator
    def check_host_or_cloud_id(cls, values):
        host, cloud_id = values.get("host"), values.get("cloud_id")
        if host == "" and cloud_id == "":
            raise ValueError("either host or cloud_id must be provided")
        return values


class ElasticProvider(BaseProvider):
    """Enrich alerts with data from Elasticsearch."""

    PROVIDER_DISPLAY_NAME = "Elastic"
    PROVIDER_CATEGORY = ["Monitoring", "Database"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._client = None

    @property
    def client(self):
        if not self._client:
            self._client = self.__initialize_client()
        return self._client

    def __initialize_client(self) -> Elasticsearch:
        """
        Initialize the ElasticSearch client for the provider.
        """
        api_key = self.config.authentication.get("api_key")
        host = self.config.authentication.get("host")
        cloud_id = self.config.authentication.get("cloud_id")

        # Elastic.co requires you to connect with cloud_id
        if cloud_id:
            es = Elasticsearch(api_key=api_key, cloud_id=cloud_id)
        # Otherwise, connect with host
        elif host:
            es = Elasticsearch(api_key=api_key, hosts=host)

        # Check if the connection was successful
        if not es.ping():
            raise ProviderConnectionFailed("Could not connect to ElasticSearch")

        return es

    def validate_config(self):
        """
        Validate the provider config.
        """
        if not self.config.authentication.get(
            "host"
        ) and not self.config.authentication.get("cloud_id"):
            raise ProviderConfigException(
                "Missing host or cloud_id in provider config",
                provider_id=self.provider_id,
            )
        if "api_key" not in self.config.authentication:
            raise ProviderConfigException(
                "Missing api_key in provider config", provider_id=self.provider_id
            )

    @staticmethod
    def get_neccessary_config_keys():
        return {
            "host": "Elastic hostname e.g host:port. for cloud_id use cloud_id",
            "api_key": "Elastic Api Key",
        }

    def dispose(self):
        """
        Dispose of the provider.
        """
        try:
            self.client.close()
        except Exception:
            self.logger.exception("Failed to close ElasticSearch client")

    def _query(self, query: str | dict, index: str = None) -> list[str]:
        """
        Query Elasticsearch index.

        Args:
            query (str | dict): The body of the query
            index (str): The index to search in

        Returns:
            list[str]: hits found by the query
        """
        # Make sure query is a dict
        if not index:
            return self._run_sql_query(query)
        else:
            return self._run_eql_query(query, index)

    def _run_sql_query(self, query: str) -> list[str]:
        response = self.client.sql.query(body={"query": query})
        import pandas as pd

        results = pd.DataFrame(response["rows"])
        columns = [col["name"] for col in response["columns"]]
        results.rename(
            columns={i: columns[i] for i in range(len(columns))}, inplace=True
        )
        return results

    def _run_eql_query(self, query: str | dict, index: str) -> list[str]:
        if isinstance(query, str):
            query = json.loads(query)

        response = self.client.search(index=index, query=query)
        self.logger.debug(
            "Got elasticsearch hits",
            extra={
                "num_of_hits": response.get("hits", {}).get("total", {}).get("value", 0)
            },
        )
        if "hits" in response and "hits" in response["hits"]:
            return response["hits"]["hits"]
        return []


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

    # e.g. https://a8723847jdfnweba687.us-central1.gcp.cloud.es.io:9243/
    elastic_cloud_id = os.environ.get("ELASTICSEARCH_CLOUD_ID")
    # e.g. NzVOSEg....== (it is base64 encoded)
    elastic_api_key = os.environ.get("ELASTICSEARCH_API_KEY")

    # Initalize the provider and provider config
    config = {
        "id": "console",
        "authentication": {
            "cloud_id": elastic_cloud_id,
            "api_key": elastic_api_key,
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="elastic",
        provider_type="elastic",
        provider_config=config,
    )
    result = provider.query('{"match_all": {}}', index="test-index")
    print(result)
