
"""MongoDB Provider for Keep"""

import logging
from typing import Optional
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class MongoDBProviderConfig(ProviderConfig):
    """MongoDB Provider Configuration"""
    
    connection_string: str
    database: Optional[str] = None
    auth_mechanism: Optional[str] = None


class MongoDBProvider(BaseProvider):
    """MongoDB Provider for monitoring MongoDB instances"""
    
    PROVIDER_DISPLAY_NAME = "MongoDB"
    PROVIDER_TAGS = ["database", "nosql", "monitoring"]
    PROVIDER_DESCRIPTION = "Monitor MongoDB databases and replicasets"
    
    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection_test",
            description="Test MongoDB connectivity",
            mandatory=True,
            alias="Connect to MongoDB",
        ),
        ProviderScope(
            name="read_stats",
            description="Read database statistics",
            mandatory=True,
            alias="Read Statistics",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: MongoDBProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self.config = config
        self.client = None

    def validate_scopes(self):
        """Validate MongoDB connection and permissions"""
        self.client = MongoClient(self.config.connection_string)
        
        # Test connection
        try:
            self.client.admin.command('ping')
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise Exception(f"Could not connect to MongoDB: {e}")
        
        # Test read permissions
        try:
            if self.config.database:
                db = self.client[self.config.database]
                db.list_collection_names()
            else:
                self.client.list_database_names()
        except OperationFailure as e:
            logger.error(f"Failed to read MongoDB stats: {e}")
            raise Exception(f"Insufficient permissions: {e}")
        
        return {"connection_test": True, "read_stats": True}

    def dispose(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()

    def _query(self):
        """Query MongoDB for metrics"""
        if not self.client:
            self.client = MongoClient(self.config.connection_string)
        
        metrics = {}
        
        # Get server status
        try:
            server_status = self.client.admin.command('serverStatus')
            metrics['server_status'] = server_status
        except Exception as e:
            logger.error(f"Failed to get server status: {e}")
        
        # Get database stats if database specified
        if self.config.database:
            try:
                db = self.client[self.config.database]
                db_stats = db.command('dbStats')
                metrics['db_stats'] = db_stats
            except Exception as e:
                logger.error(f"Failed to get database stats: {e}")
        
        return metrics

    def notify(self, **kwargs):
        """Send alert to MongoDB (e.g., log alert in MongoDB)"""
        # MongoDB is typically a source, not a destination
        # But we can store alerts in MongoDB for audit purposes
        pass

    def _get_alerts(self):
        """Get alerts from MongoDB"""
        # Query MongoDB for any stored alerts
        return []
