from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from keep.api.models.db.tenant import Tenant


class Alert(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    tenant: Tenant = Relationship()
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    provider_type: str
    # Provider id may be null if we can't correlate the alert to a specific provider
    provider_id: str | None
    event: dict = Field(sa_column=Column(JSON))

    class Config:
        arbitrary_types_allowed = True


class AlertEnrichment(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    alert_fingerprint: str
    enrichments: dict = Field(sa_column=Column(JSON))

    class Config:
        arbitrary_types_allowed = True
