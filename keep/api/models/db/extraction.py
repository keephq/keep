from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import DateTime
from sqlalchemy.sql import func
from sqlmodel import Column, Field, SQLModel


class ExtractionRule(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, default=None)
    tenant_id: str = Field(foreign_key="tenant.id")
    priority: int = Field(default=0, nullable=False)
    name: str = Field(max_length=255, nullable=False)
    description: Optional[str] = Field(max_length=2048)
    created_by: Optional[str] = Field(max_length=255)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_by: Optional[str] = Field(max_length=255)
    updated_at: Optional[datetime] = Field(
        sa_column=Column(
            DateTime(timezone=True), name="updated_at",
            onupdate=func.now(), server_default=func.now()
        )
    )
    disabled: bool = Field(default=False)
    pre: bool = Field(default=False)
    condition: Optional[str] = Field(max_length=2000)  # cel
    attribute: str = Field(max_length=255)  # the attribute to extract
    regex: str = Field(max_length=1024)  # the regex to use for extraction


class ExtractionRuleDtoBase(BaseModel):
    name: str
    description: Optional[str] = None
    priority: int = 0
    attribute: str = None
    condition: Optional[str] = None
    disabled: bool = False
    regex: str
    pre: bool = False


class ExtractionRuleDtoOut(ExtractionRuleDtoBase, extra="ignore"):
    id: int
    created_by: Optional[str]
    created_at: datetime
    updated_by: Optional[str]
    updated_at: Optional[datetime]
