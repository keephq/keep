# builtins
from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import DateTime

# third-parties
from sqlmodel import Column, Field, Index, SQLModel, func


class MaintenanceWindowRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    tenant_id: str = Field(foreign_key="tenant.id")
    description: Optional[str] = None
    created_by: str
    cel_query: str
    start_time: datetime
    end_time: datetime
    duration_seconds: Optional[int] = None
    updated_at: Optional[datetime] = Field(
        sa_column=Column(
            DateTime(timezone=True),
            name="updated_at",
            onupdate=func.now(),
            server_default=func.now(),
        )
    )
    suppress: bool = False
    enabled: bool = True

    __table_args__ = (
        Index("ix_maintenance_rule_tenant_id", "tenant_id"),
        Index("ix_maintenance_rule_tenant_id_end_time", "tenant_id", "end_time"),
    )


class MaintenanceRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    cel_query: str
    start_time: datetime
    duration_seconds: Optional[int] = None
    suppress: bool = False
    enabled: bool = True


class MaintenanceRuleRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_by: str
    cel_query: str
    start_time: datetime
    end_time: datetime
    duration_seconds: Optional[int]
    updated_at: Optional[datetime]
    suppress: bool = False
    enabled: bool = True
