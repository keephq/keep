"""
PostgresProvider is a class that provides a way to read data from Postgres and write queries to Postgres.
"""

import dataclasses
import os

import psycopg
import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import NoSchemeUrl, UrlPort


@pydantic.dataclasses.dataclass
class PostgresProviderAuthConfig:
    username: str = dataclasses.field(
        metadata={"required": True, "description": "Postgres username"}
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Postgres password",
            "sensitive": True,
        }
    )
    host: NoSchemeUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Postgres hostname",
            "validation": "no_scheme_url",
        }
    )
    database: str | None = dataclasses.field(
        metadata={"required": False, "description": "Postgres database name"},
        default=None,
    )
    port: UrlPort | None = dataclasses.field(
        default=5432,
        metadata={
            "required": False,
            "description": "Postgres port",
            "validation": "port",
        },
    )


class PostgresProvider(BaseProvider):
    """Enrich alerts with data from Postgres."""

    PROVIDER_DISPLAY_NAME = "PostgreSQL"
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
        self.conn = None

    def validate_scopes(self):
        """
        Validates that the user has the required scopes to use the provider.
        """
        try:
            conn = self.__init_connection()
            conn.close()
            scopes = {
                "connect_to_server": True,
            }
        except Exception as e:
            self.logger.exception("Error validating scopes")
            scopes = {
                "connect_to_server": str(e),
            }
        return scopes

    def __init_connection(self):
        """
        Generates a Postgres connection.

        Returns:
            psycopg2 connection object
        """
        conn = psycopg.connect(
            dbname=self.authentication_config.database,
            user=self.authentication_config.username,
            password=self.authentication_config.password,
            host=self.authentication_config.host,
            port=self.authentication_config.port,
        )
        self.conn = conn
        return conn

    def dispose(self):
        try:
            self.conn.close()
        except Exception:
            self.logger.exception("Error closing Postgres connection")

    def validate_config(self):
        """
        Validates required configuration for Postgres's provider.
        """
        self.authentication_config = PostgresProviderAuthConfig(
            **self.config.authentication
        )

    def _query(self, query: str, **kwargs: dict) -> list | tuple:
        """
        Executes a query against the Postgres database.

        Returns:
            list | tuple: list of results or single result if single_row is True
        """
        if not query:
            raise ValueError("Query is required")

        conn = self.__init_connection()
        try:
            with conn.cursor() as cur:
                # Open a cursor to perform database operations
                cur = conn.cursor()
                # Execute a simple query
                cur.execute(query)
                # Fetch the results
                results = cur.fetchall()
                # Close the cursor and connection
                cur.close()
                conn.close()
            return list(results)
        finally:
            # Close the database connection
            conn.close()

    def _notify(self, query: str, **kwargs):
        """
        Notifies the Postgres database.
        """
        # notify and query are the same for Postgres
        if not query:
            raise ValueError("Query is required")

        conn = self.__init_connection()
        try:
            with conn.cursor() as cur:
                # Open a cursor to perform database operations
                cur = conn.cursor()
                # Execute a simple query
                cur.execute(query)
                # Close the cursor and connection
                cur.close()
                conn.commit()
                conn.close()
        finally:
            # Close the database connection
            conn.close()


if __name__ == "__main__":
    config = ProviderConfig(
        authentication={
            "username": os.environ.get("POSTGRES_USER"),
            "password": os.environ.get("POSTGRES_PASSWORD"),
            "host": os.environ.get("POSTGRES_HOST"),
            "database": os.environ.get("POSTGRES_DATABASE"),
        }
    )
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    postgres_provider = PostgresProvider(context_manager, "postgres-prod", config)
    results = postgres_provider.query(query="select * from disk")
    print(results)
