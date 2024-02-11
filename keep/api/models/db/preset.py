from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlmodel import JSON, Column, Field, SQLModel


class Preset(SQLModel, table=True):
    # Unique ID for each preset
    id: str = Field(
        default_factory=lambda: str(uuid4()), primary_key=True, max_length=36
    )
    tenant_id: str = Field(foreign_key="tenant.id", index=True, max_length=36)
    name: str = Field(unique=True, max_length=256)
    options: list = Field(sa_column=Column(JSON))  # [{"label": "", "value": ""}]


class PresetDto(BaseModel, extra="ignore"):
    id: UUID
    name: str
    options: list = []


class PresetOption(BaseModel, extra="ignore"):
    label: str
    value: str
