"""
Database model for incident form schemas.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Column, Field, SQLModel

from keep.api.models.db.types import PydanticListType
from keep.api.models.incident_form_schema import FormFieldSchema


class IncidentFormSchema(SQLModel, table=True):
    """Database model for incident form schemas - multiple per tenant allowed"""
    
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
        description="Human-readable schema name"
    )
    description: Optional[str] = Field(
        default=None,
        description="Schema description"
    )
    fields: List[FormFieldSchema] = Field(
        sa_column=Column(PydanticListType(FormFieldSchema)),
        description="Form field definitions with automatic serialization"
    )
    created_by: str = Field(
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