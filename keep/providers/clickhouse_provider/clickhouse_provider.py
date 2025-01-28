"""
Clickhouse is a class that provides a way to read data from Clickhouse.
"""

import dataclasses
import os
import typing

import pydantic
from clickhouse_driver import connect
from clickhouse_driver.dbapi.extras import DictCursor

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import NoSchemeUrl, UrlPort


@pydantic.dataclasses.dataclass
class ClickhouseProviderAuthConfig:
    username: str = dataclasses.field(
        metadata={"required": True, "description": "Clickhouse username"}
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Clickhouse password",
            "sensitive": True,
        }
    )
    host: NoSchemeUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Clickhouse hostname",
            "validation": "no_scheme_url",
        }
    )
    port: UrlPort = dataclasses.field(
        metadata={
            "required": True,
            "description": "Clickhouse port",
            "validation": "port",
        }
    )
    database: str | None = dataclasses.field(
        metadata={"required": False, "description": "Clickhouse database name"},
        default=None,
    )
    protocol: typing.Literal["clickhouse", "clickhouses"] = dataclasses.field(
        default="clickhouse",
        metadata={
            "required": True,
            "description": "Protocol (Type clickhouses for SSL or clickhouse for no SSL)",
            "type": "select",
            "options": ["clickhouse", "clickhouses"],
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


class ClickhouseProvider(BaseProvider):
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
            client = self.__generate_client()

            cursor = client.cursor()
            cursor.execute("SHOW TABLES")

            tables = cursor.fetchall()
            self.logger.info(f"Tables: {tables}")

            cursor.close()
            client.close()

            scopes = {
                "connect_to_server": True,
            }
        except Exception as e:
            self.logger.exception("Error validating scopes")
            scopes = {
                "connect_to_server": str(e),
            }
        return scopes

    def __generate_client(self):
        """
        Generates a Clickhouse client.

        Returns:
            clickhouse_driver.Connection: Clickhouse connection object
        """

        user = self.authentication_config.username
        password = self.authentication_config.password
        host = self.authentication_config.host
        database = self.authentication_config.database
        port = self.authentication_config.port
        protocol = self.authentication_config.protocol
        if protocol is None:
            protocol = "clickhouse"

        if protocol not in ["clickhouse", "clickhouses"]:
            raise ProviderException("Invalid Clickhouse protocol")

        dsn = f"{protocol}://{user}:{password}@{host}:{port}/{database}"

        return connect(dsn, verify=self.authentication_config.verify)

    def dispose(self):
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
        """
        Executes a query against the Clickhouse database.

        Returns:
            list | tuple: list of results or single result if single_row is True
        """
        return self._notify(query=query, single_row=single_row, **kwargs)

    def _notify(self, query="", single_row=False, **kwargs: dict) -> list | tuple:
        """
        Executes a query against the Clickhouse database.

        Returns:
            list | tuple: list of results or single result if single_row is True
        """
        client = self.__generate_client()
        cursor = client.cursor(cursor_factory=DictCursor)

        if kwargs:
            query = query.format(**kwargs)

        cursor.execute(query)
        results = cursor.fetchall()

        cursor.close()
        if single_row:
            return results[0]

        return results


if __name__ == "__main__":
    config = ProviderConfig(
        authentication={
            "username": os.environ.get("CLICKHOUSE_USER"),
            "password": os.environ.get("CLICKHOUSE_PASSWORD"),
            "host": os.environ.get("CLICKHOUSE_HOST"),
            "database": os.environ.get("CLICKHOUSE_DATABASE"),
            "port": os.environ.get("CLICKHOUSE_PORT"),
        }
    )
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    clickhouse_provider = ClickhouseProvider(context_manager, "clickhouse-prod", config)
    results = clickhouse_provider.query(
        query="SELECT * FROM logs_table ORDER BY timestamp DESC LIMIT 1"
    )
    print(results)
