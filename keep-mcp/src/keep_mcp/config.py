from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KEEP_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    keep_api_url: str = "http://keep-backend:8080"
    keep_api_key: str = Field(
        default="",
        description="API key sent as X-API-KEY to keep-backend. Required at runtime.",
    )

    transport: Literal["stdio", "streamable-http"] = "stdio"
    http_host: str = "0.0.0.0"
    http_port: int = 8090
    http_timeout: float = 30.0

    log_level: str = "INFO"


def load_settings() -> Settings:
    return Settings()
