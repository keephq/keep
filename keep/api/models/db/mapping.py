from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel
from sqlmodel import JSON, Column, Field, SQLModel


class MappingRule(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, default=None)
    tenant_id: str = Field(foreign_key="tenant.id")
    priority: int = Field(default=0, nullable=False)
    created_by: Optional[str] = Field(max_length=255)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    disabled: bool = Field(default=False)
    # Whether this rule should override existing attributes in the alert
    override: bool = Field(default=True)
    condition: Optional[str] = Field(max_length=2000)
    # The attributes to match against (e.g. ["service","region"])
    matchers: list = Field(sa_column=Column(JSON), nullable=False)
    # The rows of the CSV file [{service: "service1", region: "region1", ...}, ...]
    rows: dict = Field(sa_column=Column(JSON), nullable=False, max_length=204800)


class MappingRuleDto(BaseModel):
    id: Optional[int] = None
    priority: int = 0
    matchers: list[str]
    rows: dict
