import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import TEXT, Column, Field, Index, SQLModel


class FacetEntityType(enum.Enum):
    INCIDENT = "incident"

class Facet(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    entity_type: str = Field(nullable=False, max_length=50)
    property_path: str = Field(nullable=False, max_length=255)
    type: str = Field(nullable=False)
    name: str = Field(max_length=255, nullable=False)
    description: Optional[str] = Field(max_length=2048)
    tenant_id: str = Field(foreign_key="tenant.id", nullable=False)
    # when
    timestamp: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    # who
    user_id: str = Field(nullable=False)

    __table_args__ = (
        Index("ix_facet_tenant_id", "tenant_id"), # we need to be able to query facets by tenant_id quickly
        Index("ix_entity_type", "entity_type"), # we need to be able to query facets by entity_type quickly
    )
