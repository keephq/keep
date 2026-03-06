"""MongoDB database provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

try:
    from pymongo import MongoClient
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False


@pydantic.dataclasses.dataclass
class MongoDBProviderAuthConfig:
    connection_string: str = dataclasses.field(
        metadata={"required": True, "description": "MongoDB Connection String", "sensitive": True},
        default=""
    )
    database: str = dataclasses.field(
        metadata={"required": True, "description": "Database Name"},
        default=""
    )

class MongoDBProvider(BaseProvider):
    """MongoDB database provider."""
    
    PROVIDER_DISPLAY_NAME = "MongoDB"
    PROVIDER_CATEGORY = ["Database"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MongoDBProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, collection: str = "", document: Dict = None, **kwargs: Dict[str, Any]):
        if not collection or not document:
            raise ProviderException("Collection and document are required")

        if not HAS_PYMONGO:
            raise ProviderException("pymongo is not installed")

        try:
            client = MongoClient(self.authentication_config.connection_string)
            db = client[self.authentication_config.database]
            result = db[collection].insert_one(document)
            client.close()
        except Exception as e:
            raise ProviderException(f"MongoDB error: {e}")

        self.logger.info("MongoDB document inserted")
        return {"status": "success", "id": str(result.inserted_id)}
