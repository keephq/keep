"""
MysqlProvider is a class that provides a way to read data from MySQL.
"""

import dataclasses
import os

import mysql.connector
import pydantic

from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MysqlProviderAuthConfig:
    username: str = dataclasses.field(
        metadata={"required": True, "description": "MySQL username"}
    )
    password: str = dataclasses.field(
        metadata={"required": True, "description": "MySQL password", "sensitive": True}
    )
    host: str = dataclasses.field(
        metadata={"required": True, "description": "MySQL hostname"}
    )
    database: str | None = dataclasses.field(
        metadata={"required": False, "description": "MySQL database name"}, default=None
    )


class MysqlProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)
        self.client = None

    def __generate_client(self) -> mysql.connector.CMySQLConnection:
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

    def _query(self, **kwargs: dict) -> list | tuple:
        """
        Executes a query against the MySQL database.

        Returns:
            list | tuple: list of results or single result if single_row is True
        """
        client = self.__generate_client()
        cursor = client.cursor()

        query = kwargs.pop("query")
        formatted_query = query.format(**kwargs)

        cursor.execute(formatted_query)
        results = cursor.fetchall()

        if kwargs.get("single_row"):
            return results[0]

        cursor.close()
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
    mysql_provider = MysqlProvider("mysql-prod", config)
    results = mysql_provider.query(query="SELECT MAX(datetime) FROM demo_table LIMIT 1")
    print(results)
