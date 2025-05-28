"""Settings module for the whole application."""

from __future__ import annotations

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

class Settings(BaseSettings):
    """Pydantic settings class for the settings module."""

    model_config = SettingsConfigDict(case_sensitive=True)

    LOG_LEVEL: str = "DEBUG"
    EVENT_GENERATOR_INTERVAL: float = 5
    EVENT_GENERATOR_PORT: int = 8081
    DEBUG: bool = True
    SAMPLE_EVENTS_FILE_PATH: str = "local_data/events.json"


config_settings = Settings()
