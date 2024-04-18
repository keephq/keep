from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlmodel import JSON, Column, Field, SQLModel


class Preset(SQLModel, table=True):
    # Unique ID for each preset
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    tenant_id: str = Field(foreign_key="tenant.id", index=True)

    # keeping index=True for better search
    created_by: Optional[str] = Field(index=True, nullable=False)
    is_private: Optional[bool] = Field(default=False)
    is_noisy: Optional[bool] = Field(default=False)
    name: str = Field(unique=True)
    options: list = Field(sa_column=Column(JSON))  # [{"label": "", "value": ""}]


class PresetDto(BaseModel, extra="ignore"):
    id: UUID
    name: str
    options: list = []
    created_by: Optional[str] = None
    is_private: Optional[bool] = Field(default=False)
    # whether the preset is noisy or not
    is_noisy: Optional[bool] = Field(default=False)
    # if true, the preset should be do noise now
    #   meaning is_noisy + at least one alert is doing noise
    should_do_noise_now: Optional[bool] = Field(default=False)
    # number of alerts
    alerts_count: Optional[int] = Field(default=0)


class PresetOption(BaseModel, extra="ignore"):
    label: str
    # cel or sql dict
    value: str | dict
