import dataclasses
import os

import pyodbc
import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import NoSchemeUrl


@pydantic.dataclasses.dataclass
class MssqlProviderAuthConfig:
    username: str = dataclasses.field(
        metadata={"required": True, "description": "MSSQL username"}
    )
    password: str = dataclasses.field(
        metadata={"required": True, "description": "MSSQL password", "sensitive": True}
    )
    host: NoSchemeUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "MSSQL hostname",
            "validation": "no_scheme_url",
        }
    )
    database: str | None = dataclasses.field(
        metadata={"required": False, "description": "MSSQL database name"}, default=None
    )
    driver: str = dataclasses.field(
        metadata={"required": False, "description": "ODBC driver name"},
        default="ODBC Driver 17 for SQL Server",
    )


class MssqlProvider(BaseProvider):
    """Enrich alerts with data from Microsoft SQL Server."""

    PROVIDER_DISPLAY_NAME = "Microsoft SQL Server"
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
        Generates a pyodbc connection to MSSQL.

        Returns:
            pyodbc.Connection: MSSQL Connection object
        """
        connection_string = (
            f"DRIVER={{{self.authentication_config.driver}}};"
            f"SERVER={self.authentication_config.host};"
            f"DATABASE={self.authentication_config.database or ''};"
            f"UID={self.authentication_config.username};"
            f"PWD={self.authentication_config.password}"
        )
        client = pyodbc.connect(connection_string)
        return client

    def dispose(self):
        """
        Disposes of the MSSQL connection if it was created.
        """
        try:
            if self.client:
                self.client.close()
        except Exception:
            self.logger.exception("Error closing MSSQL connection")

    def validate_config(self):
        """
        Validates required configuration for the MSSQL provider.
        """
        self.authentication_config = MssqlProviderAuthConfig(
            **self.config.authentication
        )

    def _notify(self, **kwargs):
        """
        For MSSQL, there is no difference if we're querying data or we want
        to make an impact. This will allow using the provider in actions
        as well as steps.
        """
        return self._query(**kwargs)

    def _query(
        self, query: str = "", as_dict: bool = False, single_row: bool = False, **kwargs
    ) -> list | tuple:
        """
        Executes a query against the MSSQL database.

        Args:
            query (str): The SQL query string.
            as_dict (bool): Whether to return rows as dictionaries.
            single_row (bool): Whether to return only the first row.

        Returns:
            list | tuple: The rows returned by the query. If single_row is
            True, a single row (dictionary or tuple) is returned.
        """
        client = self.__generate_client()

        # pyodbc does not have a built-in dict cursor like some MySQL drivers,
        # but we can emulate one if needed.
        cursor = client.cursor()

        if kwargs:
            # Basic string formatting, ensure you handle parameters safely or
            # use parameter substitution with pyodbc if dealing with user input.
            query = query.format(**kwargs)

        cursor.execute(query)
        results = []

        if as_dict:
            columns = [col[0] for col in cursor.description]
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
        else:
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
            "username": os.environ.get("MSSQL_USER"),
            "password": os.environ.get("MSSQL_PASSWORD"),
            "host": os.environ.get("MSSQL_HOST"),
            "database": os.environ.get("MSSQL_DATABASE"),
            "driver": os.environ.get("MSSQL_DRIVER", "ODBC Driver 17 for SQL Server"),
        }
    )
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    mssql_provider = MssqlProvider(context_manager, "mssql-prod", config)
    try:
        results = mssql_provider.query(query="SELECT MAX(datetime) FROM demo_table;")
        print("Query results:", results)
    except Exception as e:
        print(f"Error running MSSQL query: {e}")
