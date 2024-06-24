from datetime import datetime
from uuid import uuid4

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlmodel import Column, Field, SQLModel


class Dashboard(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    dashboard_name: str = Field(index=True)  # Index for faster uniqueness checks
    dashboard_config: dict = Field(sa_column=Column(JSON))
    created_by: str = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: str = Field(default=None)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    is_private: bool = Field(default=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "dashboard_name", name="unique_dashboard_name_per_tenant"
        ),
    )

    class Config:
        arbitrary_types_allowed = True
