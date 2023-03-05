"""
PsqlProvider is a class that provides a way to read data from Postgres.
"""

import dataclasses
import os
import pydantic

from typing import List
from psycopg2 import connect

from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PsqlProviderAuthConfig:
    user: str = dataclasses.field(
        metadata={"required": True, "description": "Postgres username"}
    )
    password: str = dataclasses.field(
        metadata={"required": True, "description": "Postgres password"}
    )
    host: str = dataclasses.field(
        metadata={"required": True, "description": "Postgres hostname"}
    )
    dbname: str | None = dataclasses.field(
        metadata={"required": False, "description": "Postgres database name"}
    )
    port: int | None = dataclasses.field(
        metadata={"required": False,
                  "description": "Postgres database name"}, default=5432)


class PsqlProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for PSQL's provider.
        """
        self.authentication_config = PsqlProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def fetch_query(self, sql_query: str, fetch_one: bool) -> List[tuple] | tuple:
        postgres_config = dataclasses.asdict(self.authentication_config)
        with connect(**postgres_config) as conn:
            with conn.cursor() as cur:
                cur.execute(sql_query)
                res = cur.fetchone() if fetch_one else cur.fetchall()
                return res

    def query(self, **kwargs: dict) -> List[tuple] | tuple:
        """
        Executes a query against the Postgres database.

        Returns:
            list | tuple: list of results or single result if single_row is True
        """

        query = kwargs.pop("query")
        fetch_all = kwargs.get('single_row', False)

        if not query:
            raise ProviderException(
                f"{self.__class__.__name__} Keyword Arguments Missing : query is required"
            )

        formatted_query = query.format(**kwargs)
        results = self.fetch_query(formatted_query, fetch_all)

        return results


if __name__ == "__main__":
    config = ProviderConfig(
        authentication={
            "user": os.environ.get("POSTGRES_USER"),
            "password": os.environ.get("POSTGRES_PASSWORD"),
            "host": os.environ.get("POSTGRES_HOST"),
            "dbname": os.environ.get("POSTGRES_DATABASE"),
        }
    )
    psql_provider = PsqlProvider("psql-prod", config)
    results = psql_provider.query(query="SELECT name FROM demo_table LIMIT 40")
    print(results)
