"""
Database model for incident form schemas.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import TEXT, func
from sqlmodel import JSON, Column, Field, SQLModel

from keep.api.models.incident_form_schema import FormFieldSchema


class IncidentFormSchema(SQLModel, table=True):
    """Database model for incident form schema - one per tenant"""
    
    __tablename__ = "incident_form_schema"
    
    tenant_id: str = Field(
        primary_key=True,
        foreign_key="tenant.id",
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
        sa_column=Column(
            "updated_at",
            default=func.now(),
            onupdate=func.now(),
            server_default=func.now()
        ),
        description="When schema was last updated"
    )
    is_active: bool = Field(
        default=True,
        description="Whether schema is active"
    )

    class Config:
        arbitrary_types_allowed = True