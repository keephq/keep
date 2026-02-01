import dataclasses
import json
import typing

import pydantic
import requests
from clickhouse_driver import connect
from clickhouse_driver.dbapi.extras import DictCursor

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import NoSchemeUrl, UrlPort


DEFAULT_TIMEOUT_SECONDS = 120  # Not to hang the thread forever, only for extreme cases


@pydantic.dataclasses.dataclass
class ClickhouseProviderAuthConfig:
    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Clickhouse username",
            "config_main_group": "authentication",
        },
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Clickhouse password",
            "sensitive": True,
            "config_main_group": "authentication",
        }
    )
    host: NoSchemeUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Clickhouse hostname",
            "validation": "no_scheme_url",
            "config_main_group": "authentication",
        }
    )
    port: UrlPort = dataclasses.field(
        metadata={
            "required": True,
            "description": "Clickhouse port",
            "validation": "port",
            "config_main_group": "authentication",
        }
    )
    database: str | None = dataclasses.field(
        metadata={"required": False, "description": "Clickhouse database name"},
        default=None,
    )
    protocol: typing.Literal["clickhouse", "clickhouses", "http", "https"] = (
        dataclasses.field(
            default="clickhouse",
            metadata={
                "required": True,
                "description": "Protocol ('clickhouses' for SSL, 'clickhouse' for no SSL, 'http' or 'https')",
                "type": "select",
                "options": ["clickhouse", "clickhouses", "http", "https"],
                "config_main_group": "authentication",
            },
        )
    )
    verify: bool = dataclasses.field(
        metadata={
            "description": "Enable SSL verification",
            "hint": "SSL verification is enabled by default",
            "type": "switch",
            "config_main_group": "authentication",
        },
        default=True,
    )


class ClickhouseProvider(BaseProvider, ProviderHealthMixin):
    """Enrich alerts with data from Clickhouse."""

    PROVIDER_DISPLAY_NAME = "Clickhouse"
    PROVIDER_CATEGORY = ["Database"]

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
        self.client = None

    def validate_scopes(self):
        """
        Validates that the user has the required scopes to use the provider.
        """
        try:
            if self._is_http_protocol():
                response = self._execute_http_query("SHOW TABLES")
                tables = response
            else:
                client = self.__generate_client()
                cursor = client.cursor()
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                cursor.close()
                client.close()

            self.logger.info(f"Tables: {tables}")

            scopes = {
                "connect_to_server": True,
            }
        except Exception as e:
            self.logger.exception("Error validating scopes")
            scopes = {
                "connect_to_server": str(e),
            }
        return scopes

    def _is_http_protocol(self) -> bool:
        """Check if the protocol is HTTP-based."""
        return self.authentication_config.protocol in ["http", "https"]

    def __generate_client(self):
        """
        Generates a Clickhouse client for native protocol.

        Returns:
            clickhouse_driver.Connection: Clickhouse connection object
        """
        if self._is_http_protocol():
            raise ProviderException("Cannot generate native client for HTTP protocol")

        user = self.authentication_config.username
        password = self.authentication_config.password
        host = self.authentication_config.host
        database = self.authentication_config.database
        port = self.authentication_config.port
        protocol = self.authentication_config.protocol

        dsn = f"{protocol}://{user}:{password}@{host}:{port}"
        if database:
            dsn += f"/{database}"
        if self.authentication_config.verify is False:
            dsn += "?verify=false"

        return connect(
            dsn,
            connect_timeout=DEFAULT_TIMEOUT_SECONDS,
            send_receive_timeout=DEFAULT_TIMEOUT_SECONDS,
            sync_request_timeout=DEFAULT_TIMEOUT_SECONDS,
            verify=self.authentication_config.verify,
        )

    def _execute_http_query(self, query: str, params: dict = None) -> list:
        """
        Execute a query using HTTP protocol.

        Args:
            query: SQL query to execute
            params: Query parameters for formatting

        Returns:
            list: Query results
        """
        protocol = self.authentication_config.protocol
        host = self.authentication_config.host
        port = self.authentication_config.port
        database = self.authentication_config.database

        url = f"{protocol}://{host}:{port}"

        # Format query if parameters are provided
        if params:
            query = query.format(**params)

        # Prepare request parameters
        request_params = {"query": query, "default_format": "JSONEachRow"}

        if database:
            request_params["database"] = database

        # Make request with authentication
        response = requests.post(
            url,
            params=request_params,
            auth=(
                self.authentication_config.username,
                self.authentication_config.password,
            ),
            verify=self.authentication_config.verify,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )

        if not response.ok:
            raise ProviderException(f"HTTP query failed: {response.text}")

        # Parse response - split by newlines as each line is a JSON object
        results = []
        for line in response.text.strip().split("\n"):
            if line:
                results.append(json.loads(line))

        return results

    def dispose(self):
        if not self._is_http_protocol() and self.client:
            try:
                self.client.close()
            except Exception:
                self.logger.exception("Error closing Clickhouse connection")

    def validate_config(self):
        """
        Validates required configuration for Clickhouse's provider.
        """
        self.authentication_config = ClickhouseProviderAuthConfig(
            **self.config.authentication
        )

    def _query(self, query="", single_row=False, **kwargs: dict) -> list | tuple:
        return self._notify(query=query, single_row=single_row, **kwargs)

    def _notify(self, query="", single_row=False, **kwargs: dict) -> list | tuple:
        """
        Executes a query against the Clickhouse database.

        Returns:
            list | tuple: list of results or single result if single_row is True
        """
        if self._is_http_protocol():
            results = self._execute_http_query(query, kwargs)
        else:
            client = self.__generate_client()
            cursor = client.cursor(cursor_factory=DictCursor)

            if kwargs:
                query = query.format(**kwargs)

            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            client.close()

        if single_row and results and len(results) > 0:
            return results[0]

        return results


if __name__ == "__main__":
    import os

    config = ProviderConfig(
        authentication={
            "username": os.environ.get("CLICKHOUSE_USER"),
            "password": os.environ.get("CLICKHOUSE_PASSWORD"),
            "host": os.environ.get("CLICKHOUSE_HOST"),
            "database": os.environ.get("CLICKHOUSE_DATABASE"),
            "port": os.environ.get("CLICKHOUSE_PORT"),
            "protocol": os.environ.get("CLICKHOUSE_PROTOCOL", "clickhouse"),
        }
    )
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    clickhouse_provider = ClickhouseProvider(context_manager, "clickhouse-prod", config)
    results = clickhouse_provider.query(
        query="SELECT * FROM Traces LIMIT 1",
        single_row=True,
    )
    print(results)
