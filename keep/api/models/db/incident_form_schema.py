"""
Database model for incident form schemas.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import TEXT, UniqueConstraint
from sqlmodel import JSON, Column, Field, SQLModel


class IncidentFormSchema(SQLModel, table=True):
    """Database model for incident form schemas - multiple per tenant allowed"""
    
    __tablename__ = "incident_form_schema"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tenant_schema_name"),
    )
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        description="Unique identifier for the schema"
    )
    tenant_id: str = Field(
        foreign_key="tenant.id",
        index=True,
        description="Tenant this schema belongs to"
    )
    name: str = Field(
        sa_column=Column(TEXT),
        description="Human-readable schema name"
    )
    description: Optional[str] = Field(
        default=None,
        sa_column=Column(TEXT),
        description="Schema description"
    )
    fields: List[dict] = Field(
        sa_column=Column(JSON),
        description="JSON array of form field definitions"
    )
    created_by: str = Field(
        sa_column=Column(TEXT),
        description="User who created the schema"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When schema was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When schema was last updated"
    )
    is_active: bool = Field(
        default=True,
        description="Whether schema is active"
    )

    class Config:
        arbitrary_types_allowed = True