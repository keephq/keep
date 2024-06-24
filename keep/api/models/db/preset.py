import enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, conint, constr
from sqlalchemy import UniqueConstraint
from sqlmodel import JSON, Column, Field, SQLModel


class StaticPresetsId(enum.Enum):
    # ID of the default preset
    FEED_PRESET_ID = "11111111-1111-1111-1111-111111111111"
    DISMISSED_PRESET_ID = "11111111-1111-1111-1111-111111111113"
    GROUPS_PRESET_ID = "11111111-1111-1111-1111-111111111114"


class Preset(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)
    # Unique ID for each preset
    id: str = Field(
        default_factory=lambda: str(uuid4()), primary_key=True, max_length=36
    )
    tenant_id: str = Field(foreign_key="tenant.id", index=True, max_length=36)
    name: str = Field(unique=True, max_length=256)

    # keeping index=True for better search
    created_by: Optional[str] = Field(index=True, nullable=False, max_length=255)
    is_private: Optional[bool] = Field(default=False)
    is_noisy: Optional[bool] = Field(default=False)
    options: list = Field(sa_column=Column(JSON))  # [{"label": "", "value": ""}]


# datatype represents a query with CEL (str) and SQL (dict)
class PresetSearchQuery(BaseModel):
    cel_query: constr(min_length=1)
    sql_query: Dict[str, Any]
    limit: conint(ge=0) = 1000
    timeframe: conint(ge=0) = 0

    class Config:
        allow_mutation = False


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
    # static presets
    static: Optional[bool] = Field(default=False)

    @property
    def cel_query(self) -> str:
        query = [
            option
            for option in self.options
            if option.get("label", "").lower() == "cel"
        ]
        if not query:
            # should not happen, maybe on old presets
            return ""
        elif len(query) > 1:
            # should not happen
            return ""
        return query[0].get("value", "")

    @property
    def sql_query(self) -> str:
        query = [
            option
            for option in self.options
            if option.get("label", "").lower() == "sql"
        ]
        if not query:
            # should not happen, maybe on old presets
            return ""
        elif len(query) > 1:
            # should not happen
            return ""
        return query[0].get("value", "")

    @property
    def query(self) -> str:
        return PresetSearchQuery(
            cel_query=self.cel_query,
            sql_query=self.sql_query,
        )


class PresetOption(BaseModel, extra="ignore"):
    label: str
    # cel or sql dict
    value: str | dict
