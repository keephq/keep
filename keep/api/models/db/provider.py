from datetime import datetime
from typing import Optional

from sqlalchemy import TEXT, UniqueConstraint
from sqlmodel import JSON, Column, Field, Index, SQLModel


class Provider(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    id: str = Field(default=None, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    name: str
    description: Optional[str]
    type: str
    installed_by: str
    installation_time: datetime
    configuration_key: str
    validatedScopes: dict = Field(
        sa_column=Column(JSON)
    )  # scope name is key and value is either True if validated or string with error message, e.g: {"read": True, "write": "error message"}
    consumer: bool = False
    pulling_enabled: bool = True
    last_pull_time: Optional[datetime]
    provisioned: bool = Field(default=False)

    class Config:
        orm_mode = True
        unique_together = ["tenant_id", "name"]


class ProviderExecutionLog(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("id"),
        Index("idx_provider_logs_tenant_provider", "tenant_id", "provider_id"),
        Index("idx_provider_logs_timestamp", "timestamp"),
    )

    id: str = Field(default=None, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    provider_id: str = Field(foreign_key="provider.id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    log_message: str = Field(sa_column=Column(TEXT))
    log_level: str = Field(default="INFO")  # INFO, WARNING, ERROR, DEBUG
    context: dict = Field(sa_column=Column(JSON), default={})
    execution_id: Optional[str] = None  # To group related logs together

    class Config:
        orm_mode = True
