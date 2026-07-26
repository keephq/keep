# builtins
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import JSON, DateTime

# third-parties
from sqlmodel import Column, Field, Index, SQLModel, func

from keep.api.models.alert import AlertStatus

DEFAULT_ALERT_STATUSES_TO_IGNORE = [
    AlertStatus.RESOLVED.value,
    AlertStatus.ACKNOWLEDGED.value,
]


class MaintenanceWindowRule(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    tenant_id: str = Field(foreign_key="tenant.id")
    description: str | None = None
    created_by: str
    cel_query: str
    start_time: datetime
    end_time: datetime
    duration_seconds: int | None = None
    updated_at: datetime | None = Field(
        sa_column=Column(
            DateTime(timezone=True),
            name="updated_at",
            onupdate=func.now(),
            server_default=func.now(),
        )
    )
    suppress: bool = False
    enabled: bool = True
    ignore_statuses: list = Field(sa_column=Column(JSON), default_factory=list)

    __table_args__ = (
        Index("ix_maintenance_rule_tenant_id", "tenant_id"),
        Index("ix_maintenance_rule_tenant_id_end_time", "tenant_id", "end_time"),
    )


class MaintenanceRuleCreate(BaseModel):
    name: str
    description: str | None = None
    cel_query: str
    start_time: datetime
    duration_seconds: int | None = None
    suppress: bool = False
    enabled: bool = True
    ignore_statuses: list[str] = DEFAULT_ALERT_STATUSES_TO_IGNORE


class MaintenanceRuleRead(BaseModel):
    id: int
    name: str
    description: str | None
    created_by: str
    cel_query: str
    start_time: datetime
    end_time: datetime
    duration_seconds: int | None
    updated_at: datetime | None
    suppress: bool = False
    enabled: bool = True
    ignore_statuses: list[str] = DEFAULT_ALERT_STATUSES_TO_IGNORE
