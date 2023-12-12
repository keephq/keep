import os
from pymongo import MongoClient
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
import pydantic
import dataclasses

@pydantic.dataclasses.dataclass
class MongoDBProviderAuthConfig:
    uri: str | None = dataclasses.field(
        metadata={"required": False, "description": "MongoDB connection URI"}
    )
    username: str = dataclasses.field(
        metadata={"required": False, "description": "MongoDB username"}
    )
    password: str = dataclasses.field(
        metadata={"required": False, "description": "MongoDB password", "sensitive": True}
    )
    host: str = dataclasses.field(
        metadata={"required": False, "description": "MongoDB hostname"}
    )
    database: str = dataclasses.field(
        metadata={"required": False, "description": "MongoDB database name"}
    )

class MongoDBProvider(BaseProvider):
    """Enrich alerts with data from MongoDB."""

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
        Generates a MongoDB client.

        Returns:
            pymongo.MongoClient: MongoDB Client
        """
        if self.authentication_config.uri:
            client = MongoClient(self.authentication_config.uri)
        else:
            client = MongoClient(
                f"mongodb://{self.authentication_config.username}:{self.authentication_config.password}@{self.authentication_config.host}/{self.authentication_config.database}"
            )
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
        self.authentication_config = MongoDBProviderAuthConfig(
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
        client = self.__generate_client()
        database = client[self.authentication_config.database]
        results = list(database.command(**query))

        if single_row:
            return results[0] if results else None

        return results


if __name__ == "__main__":
    config = ProviderConfig(
        authentication={
            "uri": os.environ.get("MONGODB_URI"),
            "username": os.environ.get("MONGODB_USER"),
            "password": os.environ.get("MONGODB_PASSWORD"),
            "host": os.environ.get("MONGODB_HOST"),
            "database": os.environ.get("MONGODB_DATABASE"),
        }
    )
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    mongodb_provider = MongoDBProvider(context_manager, "mongodb-prod", config)
    query = {"find": "restaurants", "limit": 5}
    results = mongodb_provider.query(query=query)
    print(results)
