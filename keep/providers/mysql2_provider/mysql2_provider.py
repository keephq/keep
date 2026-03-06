"""MySQL database provider."""

import dataclasses
from typing import Dict, Any, List

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False


@pydantic.dataclasses.dataclass
class MySQL2ProviderAuthConfig:
    host: str = dataclasses.field(
        metadata={"required": True, "description": "MySQL Host"},
        default=""
    )
    port: int = dataclasses.field(
        metadata={"description": "MySQL Port"},
        default=3306
    )
    database: str = dataclasses.field(
        metadata={"required": True, "description": "Database Name"},
        default=""
    )
    username: str = dataclasses.field(
        metadata={"required": True, "description": "Username"},
        default=""
    )
    password: str = dataclasses.field(
        metadata={"required": True, "description": "Password", "sensitive": True},
        default=""
    )

class MySQL2Provider(BaseProvider):
    """MySQL database provider."""
    
    PROVIDER_DISPLAY_NAME = "MySQL"
    PROVIDER_CATEGORY = ["Database"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MySQL2ProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, query: str = "", **kwargs: Dict[str, Any]):
        if not query:
            raise ProviderException("Query is required")

        if not HAS_MYSQL:
            raise ProviderException("mysql-connector-python is not installed")

        try:
            conn = mysql.connector.connect(
                host=self.authentication_config.host,
                port=self.authentication_config.port,
                database=self.authentication_config.database,
                user=self.authentication_config.username,
                password=self.authentication_config.password
            )
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            conn.commit()
            conn.close()
        except Exception as e:
            raise ProviderException(f"MySQL error: {e}")

        self.logger.info("MySQL query executed")
        return {"status": "success", "rows": len(results)}
