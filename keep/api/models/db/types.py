"""
Custom SQLAlchemy types for Keep.
"""

import logging
from typing import Type

from pydantic import BaseModel
from sqlalchemy.types import JSON, TypeDecorator

logger = logging.getLogger(__name__)


class PydanticListType(TypeDecorator):
    """
    SQLAlchemy type for storing lists of Pydantic models as JSON.
    
    This type automatically handles serialization/deserialization between
    Pydantic models and JSON storage, eliminating the need for manual
    conversion in routes and ensuring type safety.
    """
    
    impl = JSON
    cache_ok = True  # This type is safe to cache
    
    def __init__(self, pydantic_type: Type[BaseModel]):
        """
        Initialize with the Pydantic model type to use for deserialization.
        
        Args:
            pydantic_type: The Pydantic model class to deserialize to
        """
        self.pydantic_type = pydantic_type
        super().__init__()
    
    def process_bind_param(self, value, dialect):
        """
        Convert Pydantic models to dicts before storing in database.
        
        Args:
            value: List of Pydantic models or dicts
            dialect: SQLAlchemy dialect
            
        Returns:
            List of dictionaries for JSON storage
        """
        if value is None:
            return value
            
        if not isinstance(value, list):
            logger.warning(
                f"Expected list for PydanticListType, got {type(value)}"
            )
            return value
            
        result = []
        for item in value:
            if hasattr(item, 'dict') and callable(getattr(item, 'dict')):
                # It's a Pydantic model
                result.append(item.dict())
            elif isinstance(item, dict):
                # Already a dict
                result.append(item)
            else:
                # Unknown type, try to preserve it
                logger.warning(
                    f"Unexpected type in PydanticListType: {type(item)}"
                )
                result.append(item)
                
        return result
    
    def process_result_value(self, value, dialect):
        """
        Convert dicts back to Pydantic models when loading from database.
        
        Args:
            value: List of dictionaries from JSON storage
            dialect: SQLAlchemy dialect
            
        Returns:
            List of Pydantic models
        """
        if value is None:
            return value
            
        if not isinstance(value, list):
            logger.warning(
                f"Expected list from database, got {type(value)}"
            )
            return value
            
        result = []
        for item in value:
            if isinstance(item, dict):
                try:
                    # Try to create Pydantic model
                    result.append(self.pydantic_type(**item))
                except Exception as e:
                    # Log error but preserve data as dict
                    logger.error(
                        f"Failed to deserialize {self.pydantic_type.__name__}: {e}. "
                        f"Keeping as dict to prevent data loss."
                    )
                    result.append(item)
            elif isinstance(item, self.pydantic_type):
                # Already the right type (shouldn't happen but be safe)
                result.append(item)
            else:
                # Unknown type, preserve it
                logger.warning(
                    f"Unexpected type from database: {type(item)}"
                )
                result.append(item)
                
        return result