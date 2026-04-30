"""
Elasticsearch provider.

Supports Elasticsearch 7.x and 8.x clusters. The official elasticsearch-py v8
client performs a product-check handshake that rejects ES 7.x servers with an
``UnsupportedProductError``. This provider catches that error and transparently
falls back to a requests-based HTTP client so that ES 7.x on-premises deployments
work out of the box without any extra configuration.
"""

import dataclasses
import json
import typing

import pydantic
import requests as _requests
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import UnsupportedProductError

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
            "required": False,
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
    legacy_mode: bool = dataclasses.field(
        metadata={
            "description": "Enable Elasticsearch 7.x compatibility mode",
            "hint": "Enable this when connecting to an Elasticsearch 7.x cluster. The elasticsearch-py v8 client performs a strict product-check that rejects 7.x servers; this option bypasses that check.",
            "type": "switch",
        },
        default=False,
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


class _LegacyElasticSession:
    """
    Minimal HTTP session used when connecting to Elasticsearch 7.x clusters.

    elasticsearch-py v8 enforces a product-check that rejects responses from
    ES 7.x servers.  When legacy_mode is True (or auto-detected), we bypass the
    official client entirely and issue plain HTTP requests instead.
    """

    def __init__(self, host: str, auth: tuple | None, api_key: str | None, verify: bool):
        self._host = host.rstrip("/")
        self._session = _requests.Session()
        self._session.verify = verify

        if api_key:
            self._session.headers["Authorization"] = f"ApiKey {api_key}"
        elif auth:
            self._session.auth = auth

    # -- Compatibility shims used by ElasticProvider --

    def ping(self) -> bool:
        try:
            r = self._session.head(self._host, timeout=10)
            return r.status_code < 500
        except Exception:
            return False

    def info(self) -> dict:
        r = self._session.get(f"{self._host}/", timeout=10)
        r.raise_for_status()
        return r.json()

    def close(self):
        self._session.close()

    # sql.query shim
    class _Sql:
        def __init__(self, session: "_LegacyElasticSession"):
            self._s = session

        def query(self, body: dict) -> dict:
            r = self._s._session.post(
                f"{self._s._host}/_sql",
                json={"query": body.get("query")},
                params={"format": "json"},
                timeout=30,
            )
            r.raise_for_status()
            return r.json()

    @property
    def sql(self):
        return self._Sql(self)

    def search(self, index: str, query: dict, size: int = 10) -> dict:
        r = self._session.post(
            f"{self._host}/{index}/_search",
            json={"query": query, "size": size},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()


class ElasticProvider(BaseProvider):
    """Enrich alerts with data from Elasticsearch (7.x and 8.x)."""

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

    def __build_auth_tuple(self):
        u = self.authentication_config.username
        p = self.authentication_config.password
        return (u, p) if u and p else None

    def __initialize_client(self):
        """
        Initialize the Elasticsearch client.

        When ``legacy_mode`` is True the provider skips the elasticsearch-py v8
        product-check entirely and uses a lightweight requests-based session that
        is compatible with ES 7.x clusters.

        Auto-detection: if the standard ES 8 client raises ``UnsupportedProductError``
        (which ES 7.x servers always trigger), the provider automatically switches
        to legacy mode and logs an informational message.
        """
        api_key = self.authentication_config.api_key
        auth = self.__build_auth_tuple()
        host = str(self.authentication_config.host) if self.authentication_config.host else None
        cloud_id = self.authentication_config.cloud_id
        verify = self.authentication_config.verify
        legacy = self.authentication_config.legacy_mode

        if host and "cloud.es" in host and not cloud_id:
            raise ValueError(
                "Cloud ID is required for elastic.co managed elastic search"
            )

        if legacy:
            return self.__init_legacy_client(host, auth, api_key, verify)

        # Build the standard ES 8 client
        if cloud_id:
            es = (
                Elasticsearch(api_key=api_key, cloud_id=cloud_id, verify_certs=verify)
                if api_key
                else Elasticsearch(cloud_id=cloud_id, basic_auth=auth, verify_certs=verify)
            )
        elif host:
            es = (
                Elasticsearch(api_key=api_key, hosts=host, verify_certs=verify)
                if api_key
                else Elasticsearch(hosts=host, basic_auth=auth, verify_certs=verify)
            )
        else:
            raise ValueError("Missing host or cloud_id in provider config")

        try:
            es.info()
        except UnsupportedProductError:
            self.logger.info(
                "Elasticsearch 7.x detected (UnsupportedProductError from ES8 client). "
                "Switching to legacy compatibility mode automatically. "
                "You can also set 'legacy_mode: true' in the provider config to skip this probe."
            )
            return self.__init_legacy_client(host, auth, api_key, verify)
        except Exception as e:
            raise ProviderConnectionFailed(
                f"Failed to connect to Elasticsearch: {str(e)}"
            )

        return es

    def __init_legacy_client(self, host, auth, api_key, verify) -> _LegacyElasticSession:
        """Create and verify a legacy (ES 7.x) HTTP session."""
        if not host:
            raise ProviderConnectionFailed(
                "legacy_mode requires a 'host' URL (cloud_id is not supported for ES 7.x)"
            )
        client = _LegacyElasticSession(host, auth, api_key, verify)
        try:
            client.info()
        except Exception as e:
            raise ProviderConnectionFailed(
                f"Failed to connect to Elasticsearch (legacy mode): {str(e)}"
            )
        return client

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
            self.logger.exception("Failed to close Elasticsearch client")

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
            _size = query.get("size", 10)
        else:
            _query_to_run = query
            _size = query.get("size", 10)
        response = self.client.search(index=index, query=_query_to_run, size=_size)
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
    index = "keep-alerts-keep"
    query = """{
              "size": "1000",
              "query": {
                    "query_string": {
                    "query": "firing"
                }
              }
    }"""

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="elastic",
        provider_type="elastic",
        provider_config=config,
    )
    result = provider.query(query=query, index=index)
    print(result)
