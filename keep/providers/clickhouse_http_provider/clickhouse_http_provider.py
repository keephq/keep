"""
Clickhouse is a class that provides a way to read data from Clickhouse.
"""

import asyncio
import pydantic
import dataclasses

import clickhouse_connect

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import NoSchemeUrl, UrlPort


@pydantic.dataclasses.dataclass
class ClickhouseHttpProviderAuthConfig:
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


class ClickhouseHttpProvider(BaseProvider):
    """Enrich alerts with data from Clickhouse."""

    PROVIDER_DISPLAY_NAME = "Clickhouse Http"
    PROVIDER_CATEGORY = ["Database"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connect_to_server",
            description="The user can connect to the server",
            mandatory=True,
            alias="Connect to the server",
        )
    ]
    SHARED_CLIENT = {}  # Caching the client to avoid creating a new one for each query

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.client = None

    def dispose(self):
        pass

    def validate_scopes(self):
        """
        Validates that the user has the required scopes to use the provider.
        """
        try:
            client = asyncio.run(self.__generate_client())

            tables = result = asyncio.run(client.query("SHOW TABLES"))
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

    async def __generate_client(self):
        """
        Generates a Clickhouse client.
        """
        if self.context_manager.tenant_id + self.provider_id in ClickhouseHttpProvider.SHARED_CLIENT:
            return ClickhouseHttpProvider.SHARED_CLIENT[self.context_manager.tenant_id + self.provider_id]

        user = self.authentication_config.username
        password = self.authentication_config.password
        host = self.authentication_config.host
        database = self.authentication_config.database
        port = self.authentication_config.port

        client = await clickhouse_connect.get_async_client(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
        ClickhouseHttpProvider.SHARED_CLIENT[self.context_manager.tenant_id + self.provider_id] = client

        return client

    def validate_config(self):
        """
        Validates required configuration for Clickhouse's provider.
        """
        self.authentication_config = ClickhouseHttpProviderAuthConfig(
            **self.config.authentication
        )
        return True

    async def _query(self, query="", single_row=False, **kwargs: dict) -> list | tuple:
        """
        Executes a query against the Clickhouse database.
        Returns:
            list | tuple: list of results or single result if single_row is True
        """
        return await self._notify(query=query, single_row=single_row, **kwargs)

    async def _notify(self, query="", single_row=False, **kwargs: dict) -> list | tuple:
        """
        Executes a query against the Clickhouse database.
        Returns:
            list | tuple: list of results or single result if single_row is True
        """
        # return {'dt': datetime.datetime(2024, 12, 4, 6, 37, 22), 'customer_id': 99999999, 'total_spent': 19.850000381469727}
        client = await self.__generate_client()
        results = await client.query(query, **kwargs)
        rows = results.result_rows
        columns = results.column_names

        # Making the results more human readable and compatible with the format we had with sync library before.
        results = [dict(zip(columns, row)) for row in rows]

        if single_row:
            return results[0]

        return results