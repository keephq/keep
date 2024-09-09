from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, validator
from sqlmodel import JSON, Column, Field, SQLModel


class MappingRule(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, default=None)
    tenant_id: str = Field(foreign_key="tenant.id", max_length=36)
    priority: int = Field(default=0, nullable=False)
    name: str = Field(max_length=255, nullable=False)
    description: Optional[str] = Field(max_length=2048)
    file_name: Optional[str] = Field(max_length=255)
    created_by: Optional[str] = Field(max_length=255)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    disabled: bool = Field(default=False)
    # Whether this rule should override existing attributes in the alert
    override: bool = Field(default=True)
    condition: Optional[str] = Field(max_length=2000)
    # The type of this mapping rule
    type: str = "csv"
    # The attributes to match against (e.g. ["service","region"])
    matchers: list[str] = Field(sa_column=Column(JSON), nullable=False)
    # The rows of the CSV file [{service: "service1", region: "region1", ...}, ...]
    rows: Optional[list[dict]] = Field(
        sa_column=Column(JSON),
        nullable=True,
    )  # max_length=204800)
    updated_by: Optional[str] = Field(max_length=255, default=None)
    last_updated_at: datetime = Field(default_factory=datetime.utcnow)


class MappRuleDtoBase(BaseModel):
    name: str
    description: Optional[str] = None
    file_name: Optional[str] = None
    priority: int = 0
    matchers: list[str]
    type: Literal["csv", "topology"] = "csv"


class MappingRuleDtoOut(MappRuleDtoBase, extra="ignore"):
    id: int
    created_by: Optional[str]
    created_at: datetime
    attributes: list[str] = []
    updated_by: Optional[str] | None
    last_updated_at: Optional[datetime] | None


class MappingRuleDtoIn(MappRuleDtoBase):
    rows: Optional[list[dict]] = None

    @validator("type", pre=True, always=True)
    def validate_type(cls, _type, values):
        if _type == "csv" and not values.get("rows"):
            raise ValueError("Mapping of type CSV cannot have empty rows")
        return _type
