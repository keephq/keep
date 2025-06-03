"""Settings module for the whole application."""

from __future__ import annotations

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

class Settings(BaseSettings):
    """Pydantic settings class for the settings module."""

    model_config = SettingsConfigDict(case_sensitive=True)

    LOG_LEVEL: str = "DEBUG"
    INCIDENT_MANAGER_PORT: int = 8082
    DEBUG: bool = True
    VECTOR_DB_COLLECTION_NAME: str = "incidents"
    EMBEDDING_DIMENSION: int = 1536
    SIMILARITY_CUTOFF: float = 0.9
    SIMILARITY_TOP_K: int = 15
    VECTOR_DB_URL: str = "/data/milvus_vector_db.db"


config_settings = Settings()
