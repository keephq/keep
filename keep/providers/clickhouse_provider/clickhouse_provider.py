"""
Clickhouse is a class that provides a way to read data from Clickhouse.
"""

import dataclasses
import os

import pydantic

from clickhouse_driver import connect
from clickhouse_driver.dbapi.extras import DictCursor

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class ClickhouseProviderAuthConfig:
    username: str = dataclasses.field(
        metadata={"required": True, "description": "Clickhouse username"}
    )
    password: str = dataclasses.field(
        metadata={"required": True, "description": "Clickhouse password", "sensitive": True}
    )
    host: str = dataclasses.field(
        metadata={"required": True, "description": "Clickhouse hostname"}
    )
    port: str = dataclasses.field(
        metadata={"required": True, "description": "Clickhouse port"}
    )
    database: str | None = dataclasses.field(
        metadata={"required": False, "description": "Clickhouse database name"}, default=None
    )


class ClickhouseProvider(BaseProvider):
    """Enrich alerts with data from Clickhouse."""

    PROVIDER_DISPLAY_NAME = "Clickhouse"

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
            cursor.execute('SHOW TABLES')
            
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

        user=self.authentication_config.username
        password=self.authentication_config.password
        host=self.authentication_config.host
        database=self.authentication_config.database
        port=self.authentication_config.port

        dsn = f"clickhouse://{user}:{password}@{host}:{port}/{database}"

        return connect(dsn)

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

    def _notify(
        self, query="", single_row=False, **kwargs: dict
    ) -> list | tuple:
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
        }
    )
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    clickhouse_provider = ClickhouseProvider(context_manager, "clickhouse-prod", config)
    results = clickhouse_provider.query(query="SELECT * FROM logs_table ORDER BY timestamp DESC LIMIT 1")
    print(results)
