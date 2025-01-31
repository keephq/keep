"""
MysqlProvider is a class that provides a way to read data from MySQL.
"""

import dataclasses
import os

import mysql.connector
import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import NoSchemeUrl


@pydantic.dataclasses.dataclass
class MysqlProviderAuthConfig:
    username: str = dataclasses.field(
        metadata={"required": True, "description": "MySQL username"}
    )
    password: str = dataclasses.field(
        metadata={"required": True, "description": "MySQL password", "sensitive": True}
    )
    host: NoSchemeUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "MySQL hostname",
            "validation": "no_scheme_url",
        }
    )
    database: str | None = dataclasses.field(
        metadata={"required": False, "description": "MySQL database name"}, default=None
    )


class MysqlProvider(BaseProvider):
    """Enrich alerts with data from MySQL."""

    PROVIDER_DISPLAY_NAME = "MySQL"
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
        Generates a MySQL client.

        Returns:
            mysql.connector.CMySQLConnection: MySQL Client
        """
        client = mysql.connector.connect(
            user=self.authentication_config.username,
            password=self.authentication_config.password,
            host=self.authentication_config.host,
            database=self.authentication_config.database,
        )
        return client

    def dispose(self):
        try:
            self.client.close()
        except Exception:
            self.logger.exception("Error closing MySQL connection")

    def validate_config(self):
        """
        Validates required configuration for MySQL's provider.
        """
        self.authentication_config = MysqlProviderAuthConfig(
            **self.config.authentication
        )
        
    def _notify(self, **kwargs):
        """
        For MySQL there is no difference if we're querying data or we want to make an impact.
        This will allow using the provider in actions as well as steps.
        """
        return self._query(**kwargs)

    def _query(
        self, query="", as_dict=False, single_row=False, **kwargs: dict
    ) -> list | tuple:
        """
        Executes a query against the MySQL database.

        Returns:
            list | tuple: list of results or single result if single_row is True
        """
        client = self.__generate_client()
        cursor = client.cursor(dictionary=as_dict)

        if kwargs:
            query = query.format(**kwargs)

        cursor.execute(query)
        results = cursor.fetchall()

        cursor.close()
        if single_row:
            if results:
                return results[0]
            else:
                self.logger.warning("No results found for query: %s", query)
                raise ValueError(f"Query {query} returned no rows")

        return results


if __name__ == "__main__":
    config = ProviderConfig(
        authentication={
            "username": os.environ.get("MYSQL_USER"),
            "password": os.environ.get("MYSQL_PASSWORD"),
            "host": os.environ.get("MYSQL_HOST"),
            "database": os.environ.get("MYSQL_DATABASE"),
        }
    )
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    mysql_provider = MysqlProvider(context_manager, "mysql-prod", config)
    results = mysql_provider.query(query="SELECT MAX(datetime) FROM demo_table LIMIT 1")
    print(results)
