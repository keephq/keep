from uuid import UUID, uuid4
from typing import Optional
from pydantic import BaseModel
from sqlmodel import JSON, Column, Field, SQLModel


class Preset(SQLModel, table=True):
    # Unique ID for each preset
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    tenant_id: str = Field(foreign_key="tenant.id", index=True)

    # if created_by is not null then it means this preset is only for this user
    # keeping index=True for better search
    created_by: Optional[str] = Field(index=True, nullable=True)
    name: str = Field(unique=True)
    options: list = Field(sa_column=Column(JSON))  # [{"label": "", "value": ""}]


class PresetDto(BaseModel, extra="ignore"):
    id: UUID
    name: str
    options: list = []
    created_by: Optional[str] = None


class PresetOption(BaseModel, extra="ignore"):
    label: str
    value: str
