"""
MongodbProvider is a class that provides a way to read data from MySQL.
"""

import dataclasses
import json
import os

import pydantic
from pymongo import MongoClient

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import MultiHostUrl


@pydantic.dataclasses.dataclass
class MongodbProviderAuthConfig:
    host: MultiHostUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Mongo host_uri",
            "hint": "mongodb+srv://host:port, mongodb://host1:port1,host2:port2?authSource",
            "validation": "multihost_url",
        }
    )
    username: str = dataclasses.field(
        metadata={"required": False, "description": "MongoDB username"}, default=None
    )
    password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "MongoDB password",
            "sensitive": True,
        },
        default=None,
    )
    database: str = dataclasses.field(
        metadata={"required": False, "description": "MongoDB database name"},
        default=None,
    )
    auth_source: str | None = dataclasses.field(
        metadata={"required": False, "description": "Mongo authSource database name"},
        default=None,
    )
    additional_options: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Mongo kwargs, these will be passed to MongoClient",
        },
        default=None,
    )


class MongodbProvider(BaseProvider):
    """Enrich alerts with data from MongoDB."""

    PROVIDER_DISPLAY_NAME = "MongoDB"
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
            client.admin.command(
                "ping"
            )  # will raise an exception if the server is not available
            client.close()
            scopes = {
                "connect_to_server": True,
            }
        except Exception:
            self.logger.exception("Error validating scopes")
            scopes = {
                "connect_to_server": "Unable to connect to server. Please check the connection details.",
            }
        return scopes

    def __generate_client(self):
        """
        Generates a MongoDB client.

        Returns:
            pymongo.MongoClient: MongoDB Client
        """
        # removing all None fields, as mongo will not accept None fields}
        if self.authentication_config.additional_options:
            try:
                self.logger.debug("Casting the additional_options to dict")
                additional_options = json.loads(
                    self.authentication_config.additional_options
                )
                self.logger.debug("Successfully casted the additional_options to dict")
            except Exception:
                self.logger.debug("Failed to cast the additional_options to dict")
                raise ValueError("additional_options must be a valid dict")
        else:
            additional_options = {}

        client_conf = {
            k: v
            for k, v in self.authentication_config.__dict__.items()
            if v
            and not k.startswith("__pydantic")  # removing pydantic default key
            and k != "additional_options"  # additional_options will go seperately
            and k != "database"
        }  # database is not a valid mongo option
        client = MongoClient(
            **client_conf, **additional_options, serverSelectionTimeoutMS=10000
        )  # 10 seconds timeout
        return client

    def dispose(self):
        try:
            self.client.close()
        except Exception:
            self.logger.exception("Error closing MongoDB connection")

    def validate_config(self):
        """
        Validates required configuration for MongoDB's provider.
        """
        host = self.config.authentication["host"]
        if host is None:
            raise ProviderConfigException("Please provide a value for `host`")
        if not host.strip():
            raise ProviderConfigException("Host cannot be empty")
        if not (host.startswith("mongodb://") or host.startswith("mongodb+srv://")):
            host = f"mongodb://{host}"

        self.authentication_config = MongodbProviderAuthConfig(
            **self.config.authentication
        )

    def _query(
        self, query: dict, as_dict=False, single_row=False, **kwargs: dict
    ) -> list | tuple:
        """
        Executes a query against the MongoDB database.

        Returns:
            list | tuple: list of results or single result if single_row is True
        """
        if isinstance(query, str):
            query = json.loads(query)
            
        client = self.__generate_client()
        database = client[self.authentication_config.database]
        results = list(database.cursor_command(query))

        if single_row:
            return results[0] if results else None

        return results


if __name__ == "__main__":
    config = ProviderConfig(
        authentication={
            "host": os.environ.get("MONGODB_HOST"),
            "username": os.environ.get("MONGODB_USER"),
            "password": os.environ.get("MONGODB_PASSWORD"),
            "database": os.environ.get("MONGODB_DATABASE"),
            # "additional_options": '{"retryWrites": false}',
        }
    )
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    mongodb_provider = MongodbProvider(context_manager, "mongodb-prod", config)
    query = {"find": "restaurants", "limit": 5}
    results = mongodb_provider.query(query=query)
    print(results)
