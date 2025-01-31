import enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, conint, constr
from sqlalchemy import UniqueConstraint
from sqlmodel import JSON, Column, Field, Relationship, SQLModel


class StaticPresetsId(enum.Enum):
    # ID of the default preset
    FEED_PRESET_ID = "11111111-1111-1111-1111-111111111111"
    DISMISSED_PRESET_ID = "11111111-1111-1111-1111-111111111113"
    GROUPS_PRESET_ID = "11111111-1111-1111-1111-111111111114"
    WITHOUT_INCIDENT_PRESET_ID = "11111111-1111-1111-1111-111111111115"


def generate_uuid():
    return str(uuid4())


class PresetTagLink(SQLModel, table=True):
    tenant_id: str = Field(foreign_key="tenant.id", primary_key=True)
    preset_id: UUID = Field(foreign_key="preset.id", primary_key=True)
    tag_id: str = Field(foreign_key="tag.id", primary_key=True)


class Tag(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    name: str = Field(unique=True, nullable=False)
    presets: List["Preset"] = Relationship(
        back_populates="tags", link_model=PresetTagLink
    )


class TagDto(BaseModel):
    id: Optional[str]  # for new tag from the frontend, the id would be None
    name: str


class Preset(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id", index=True)
    created_by: Optional[str] = Field(index=True, nullable=False)
    is_private: Optional[bool] = Field(default=False)
    is_noisy: Optional[bool] = Field(default=False)
    name: str = Field(unique=True)
    options: list = Field(sa_column=Column(JSON))  # [{"label": "", "value": ""}]
    tags: List[Tag] = Relationship(
        back_populates="presets",
        link_model=PresetTagLink,
        sa_relationship_kwargs={"lazy": "joined"},
    )

    def to_dict(self):
        """Convert the model to a dictionary including relationships."""
        preset_dict = self.dict()
        preset_dict["tags"] = [tag.dict() for tag in self.tags]
        return preset_dict


# datatype represents a query with CEL (str) and SQL (dict)
class PresetSearchQuery(BaseModel):
    cel_query: constr(min_length=0)
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
    tags: List[TagDto] = []

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
    def query(self) -> PresetSearchQuery:
        return PresetSearchQuery(
            cel_query=self.cel_query,
            sql_query=self.sql_query,
        )


class PresetOption(BaseModel, extra="ignore"):
    label: str
    # cel or sql dict
    value: str | dict
