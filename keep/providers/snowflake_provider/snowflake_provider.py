"""
SnowflakeProvider is a class that provides a way to read data from Snowflake.
"""

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from snowflake.connector import connect
from snowflake.connector.connection import SnowflakeConnection

from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


class SnowflakeProvider(BaseProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.client = self.__generate_client()

    def __generate_client(self) -> SnowflakeConnection:
        """
        Generates a Snowflake connection.

        Returns:
            SnowflakeConnection: The connection to Snowflake.
        """
        # Todo: support username/password authentication
        encoded_private_key = self.config.authentication.get("pkey").encode()
        private_key = serialization.load_pem_private_key(
            encoded_private_key,
            password=self.config.authentication.get("pkey_passphrase"),
            backend=default_backend(),
        )

        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        snowflake_connection = connect(
            user=self.config.authentication.get("user"),
            account=self.config.authentication.get("account"),
            private_key=private_key_bytes,
        )
        return snowflake_connection

    def validate_config(self):
        """
        Validates required configuration for Snowflake's provider.

        Raises:
            ProviderConfigException: user or account is missing in authentication.
            ProviderConfigException: private key
        """
        if (
            "user" not in self.config.authentication
            or "account" not in self.config.authentication
        ):
            raise ProviderConfigException("missing user or account in authentication")
        if (
            "pkey" not in self.config.authentication
            and "password" not in self.config.authentication
        ):
            raise ProviderConfigException("missing pkey or password in authentication")

    def query(self, query: str, **kwargs: dict):
        """
        Query snowflake using the given query

        Args:
            query (str): query to execute

        Returns:
            list[tuple] | list[dict]: results of the query
        """
        cursor = self.client.cursor()
        return cursor.execute(query.format(**kwargs)).fetchall()


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    snowflake_private_key = os.environ.get("SNOWFLAKE_PRIVATE_KEY")
    snowflake_account = os.environ.get("SNOWFLAKE_ACCOUNT")

    config = {
        "id": "snowflake-prod",
        "provider_type": "snowflake",
        "authentication": {
            "user": "dbuser",
            "account": snowflake_account,
            "pkey": snowflake_private_key,
        },
    }
    provider = ProvidersFactory.get_provider(config)
    result = provider.query(
        "select * from {table} limit 10", table="TEST_DB.PUBLIC.CUSTOMERS"
    )
    print(result)
