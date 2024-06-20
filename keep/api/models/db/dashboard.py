from datetime import datetime
from uuid import uuid4

from sqlmodel import JSON, Column, Field, SQLModel


class Dashboard(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    dashboard_name: str
    dashboard_config: dict = Field(sa_column=Column(JSON))
    created_by: str = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    is_private: bool = Field(default=False)

    class Config:
        arbitrary_types_allowed = True
