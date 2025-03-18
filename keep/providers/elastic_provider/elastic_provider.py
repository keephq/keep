"""
Elasticsearch provider.
"""

import dataclasses
import json
import typing

import pydantic
from elasticsearch import Elasticsearch

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_connection_failed import ProviderConnectionFailed
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class ElasticProviderAuthConfig:
    """Elasticsearch authentication configuration."""

    host: pydantic.AnyHttpUrl | None = dataclasses.field(
        default=None,
        metadata={
            "required": True,
            "description": "Elasticsearch host",
            "validation": "any_http_url",
        },
    )
    cloud_id: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Elasticsearch cloud id",
            "hint": "Required for elastic.co managed elastic - should be smth like clustername-prod:dXMtY2....==",
        },
    )
    verify: bool = dataclasses.field(
        metadata={
            "description": "Enable SSL verification",
            "hint": "SSL verification is enabled by default",
            "type": "switch",
        },
        default=True,
    )
    api_key: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "description": "Elasticsearch API Key",
            "sensitive": True,
            "config_sub_group": "api_key",
            "config_main_group": "authentication",
            "hint": "Should be the encoded api key in base64",
        },
    )
    username: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "description": "Elasticsearch username",
            "config_sub_group": "username_password",
            "config_main_group": "authentication",
        },
    )
    password: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "description": "Elasticsearch password",
            "sensitive": True,
            "config_sub_group": "username_password",
            "config_main_group": "authentication",
        },
    )

    @pydantic.root_validator
    def check_api_key_or_username_password(cls, values):
        api_key = values.get("api_key")
        username = values.get("username")
        password = values.get("password")
        if api_key is None and username is None and password is None:
            raise ValueError(
                "Missing api_key or username and password in provider config"
            )
        return values

    @pydantic.root_validator
    def check_host_or_cloud_id(cls, values):
        host, cloud_id = values.get("host"), values.get("cloud_id")
        if host is None and cloud_id is None:
            raise ValueError("Missing host or cloud_id in provider config")
        return values


class ElasticProvider(BaseProvider):
    """Enrich alerts with data from Elasticsearch."""

    PROVIDER_DISPLAY_NAME = "Elastic"
    PROVIDER_CATEGORY = ["Monitoring", "Database"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connect_to_server",
            description="The user can connect to the server",
            mandatory=True,
            alias="Connect to the server",
        )
    ]

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
        api_key = self.authentication_config.api_key
        username = self.authentication_config.username
        password = self.authentication_config.password
        host = self.authentication_config.host
        cloud_id = self.authentication_config.cloud_id

        if "cloud.es" in host and not cloud_id:
            raise ValueError(
                "Cloud ID is required for elastic.co managed elastic search"
            )

        # Elastic.co requires you to connect with cloud_id
        if cloud_id:
            es = (
                Elasticsearch(
                    api_key=api_key,
                    cloud_id=cloud_id,
                    verify_certs=self.authentication_config.verify,
                )
                if api_key
                else Elasticsearch(
                    cloud_id=cloud_id,
                    basic_auth=(username, password),
                    verify_certs=self.authentication_config.verify,
                )
            )
        # Otherwise, connect with host
        elif host:
            es = (
                Elasticsearch(
                    api_key=api_key,
                    hosts=host,
                    verify_certs=self.authentication_config.verify,
                )
                if api_key
                else Elasticsearch(
                    hosts=host,
                    basic_auth=(username, password),
                    verify_certs=self.authentication_config.verify,
                )
            )
        else:
            raise ValueError("Missing host or cloud_id in provider config")

        # Check if the connection was successful
        try:
            es.info()
        except Exception as e:
            raise ProviderConnectionFailed(
                f"Failed to connect to ElasticSearch: {str(e)}"
            )

        return es

    def validate_config(self):
        """
        Validate the provider config.
        """
        self.authentication_config = ElasticProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """
        Validate that the user has the required scopes to use the provider.
        """
        # implement
        try:
            self.client.ping()
            scopes = {
                "connect_to_server": True,
            }
        except Exception as e:
            self.logger.exception("Error validating scopes")
            scopes = {
                "connect_to_server": str(e),
            }
        return scopes

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

        # @tb: I removed pandas so if we'll have performance issues we can revert to pandas
        # Original pandas implementation:
        # import pandas as pd
        # results = pd.DataFrame(response["rows"])
        # columns = [col["name"] for col in response["columns"]]
        # results.rename(
        #     columns={i: columns[i] for i in range(len(columns))}, inplace=True
        # )
        # return results

        # Convert rows to list of dicts with proper column names
        columns = [col["name"] for col in response["columns"]]
        results = []
        for row in response["rows"]:
            result = {}
            for i, value in enumerate(row):
                result[columns[i]] = value
            results.append(result)

        return results

    def _run_eql_query(self, query: str | dict, index: str) -> list[str]:
        if isinstance(query, str):
            query = json.loads(query)
        if "query" in query:
            _query_to_run = query.get("query")
        else:
            _query_to_run = query
        response = self.client.search(index=index, query=_query_to_run)
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
