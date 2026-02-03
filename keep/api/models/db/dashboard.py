from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from typing import Dict, Any, Optional

from sqlalchemy import Column, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Dashboard(SQLModel, table=True):
    """
    Tenant-scoped dashboard definition.

    - Dashboard names are unique per tenant
    - Config is stored as structured JSON
    - Supports soft lifecycle control
    """

    __tablename__ = "dashboard"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, index=True)

    tenant_id: str = Field(
        foreign_key="tenant.id",
        nullable=False,
        index=True,
        max_length=64,
    )

    dashboard_name: str = Field(
        nullable=False,
        index=True,
        max_length=128,
    )

    dashboard_config: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False),
    )

    created_by: Optional[str] = Field(default=None, index=True, max_length=64)
    created_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)

    updated_by: Optional[str] = Field(default=None, index=True, max_length=64)
    updated_at: datetime = Field(
        default_factory=utcnow,
        nullable=False,
        index=True,
        sa_column_kwargs={"onupdate": utcnow},
    )

    # Lifecycle / visibility
    is_active: bool = Field(default=True, nullable=False, index=True)
    is_private: bool = Field(default=False, nullable=False, index=True)

    # Optional soft delete (future-proofing)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True, index=True)

    __table_args__ = (
        # Enforce uniqueness per tenant
        UniqueConstraint(
            "tenant_id",
            "dashboard_name",
            name="uq_dashboard_tenant_name",
        ),
        # Common query patterns
        Index(
            "ix_dashboard_tenant_active",
            "tenant_id",
            "is_active",
        ),
        Index(
            "ix_dashboard_tenant_visibility",
            "tenant_id",
            "is_private",
        ),
    )