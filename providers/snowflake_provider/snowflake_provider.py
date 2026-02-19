"""
SnowflakeProvider is a class that provides a way to read data from Snowflake.
"""

import dataclasses
import typing

import pydantic
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from snowflake.connector import connect
from snowflake.connector.connection import SnowflakeConnection

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class SnowflakeProviderAuthConfig:
    user: str = dataclasses.field(
        metadata={"required": True, "description": "Snowflake user"}
    )
    account: str = dataclasses.field(
        metadata={"required": True, "description": "Snowflake account"}
    )
    pkey: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Snowflake private key",
            "sensitive": True,
        }
    )
    pkey_passphrase: typing.Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "Snowflake password",
            "sensitive": True,
        },
        default=None,
    )


class SnowflakeProvider(BaseProvider):
    """Enrich alerts with data from Snowflake."""

    PROVIDER_DISPLAY_NAME = "Snowflake"
    PROVIDER_CATEGORY = ["Database"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._client = None

    @property
    def client(self) -> SnowflakeConnection:
        if self._client is None:
            self._client = self.__generate_client()
        return self._client

    def __generate_client(self) -> SnowflakeConnection:
        """
        Generates a Snowflake connection.

        Returns:
            SnowflakeConnection: The connection to Snowflake.
        """
        # Todo: support username/password authentication
        encoded_private_key = self.authentication_config.pkey.encode()
        encoded_password = (
            self.authentication_config.pkey_passphrase.encode()
            if self.authentication_config.pkey_passphrase
            else None
        )
        private_key = serialization.load_pem_private_key(
            encoded_private_key,
            password=encoded_password,
            backend=default_backend(),
        )

        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        snowflake_connection = connect(
            user=self.authentication_config.user,
            account=self.authentication_config.account,
            private_key=private_key_bytes,
        )
        return snowflake_connection

    def dispose(self):
        try:
            self.client.close()
        except Exception:
            self.logger.exception("Error closing Snowflake connection")

    def validate_config(self):
        """
        Validates required configuration for Snowflake's provider.

        Raises:
            ProviderConfigException: user or account is missing in authentication.
            ProviderConfigException: private key
        """
        self.authentication_config = SnowflakeProviderAuthConfig(
            **self.config.authentication
        )

    def _query(self, query: str, **kwargs: dict):
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
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    snowflake_private_key = os.environ.get("SNOWFLAKE_PRIVATE_KEY")
    snowflake_account = os.environ.get("SNOWFLAKE_ACCOUNT")

    config = {
        "id": "snowflake-prod",
        "authentication": {
            "user": "dbuser",
            "account": snowflake_account,
            "pkey": snowflake_private_key,
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="snowflake",
        provider_type="snowflake",
        provider_config=config,
    )
    result = provider.query(
        "select * from {table} limit 10", table="TEST_DB.PUBLIC.CUSTOMERS"
    )
    print(result)
