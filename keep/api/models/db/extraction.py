from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, UniqueConstraint
from sqlalchemy.sql import func
from sqlmodel import Column, Field, SQLModel


class ExtractionRule(SQLModel, table=True):
    __tablename__ = "extraction_rule"
    # If you want unique rule names per tenant, uncomment:
    # __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_extraction_rule_tenant_name"),)

    id: Optional[int] = Field(default=None, primary_key=True)

    tenant_id: str = Field(foreign_key="tenant.id", nullable=False, index=True)

    priority: int = Field(default=0, nullable=False)

    name: str = Field(max_length=255, nullable=False)
    description: Optional[str] = Field(default=None, max_length=2048)

    created_by: Optional[str] = Field(default=None, max_length=255)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    )

    updated_by: Optional[str] = Field(default=None, max_length=255)
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )
    )

    disabled: bool = Field(default=False, nullable=False)
    pre: bool = Field(default=False, nullable=False)

    condition: Optional[str] = Field(default=None, max_length=2000)  # CEL
    attribute: str = Field(max_length=255, nullable=False)
    regex: str = Field(max_length=1024, nullable=False)


class ExtractionRuleDtoBase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    description: Optional[str] = None
    priority: int = 0
    attribute: str  # required
    condition: Optional[str] = None
    disabled: bool = False
    regex: str
    pre: bool = False


class ExtractionRuleDtoOut(ExtractionRuleDtoBase):
    id: int
    created_by: Optional[str] = None
    created_at: datetime
    updated_by: Optional[str] = None
    updated_at: datetime
