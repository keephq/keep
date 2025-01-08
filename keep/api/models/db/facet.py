import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import TEXT, Column, Field, Index, SQLModel


class FacetEntityType(enum.Enum):
    INCIDENT = "incident"

class Facet(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    target_entity = Field(nullable=False)
    property_path = Field(nullable=False)
    type = Field(nullable=False)
    name = Field(nullable=False)
    description = Field(sa_column=Column(TEXT))
    tenant_id: str = Field(foreign_key="tenant.id", nullable=False)
    # when
    timestamp: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    # who
    user_id: str = Field(nullable=False)

    __table_args__ = (
        Index("ix_alert_audit_tenant_id", "tenant_id"),
    )
