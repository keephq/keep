from typing import Any

import pydantic
from pydantic import BaseModel

from keep.api.models.db.facet import FacetType


class FacetOptionsQueryDto(BaseModel):
    cel: str | None
    facet_queries: dict[str, str] | None


class FacetOptionDto(BaseModel):
    display_name: str
    value: Any
    matches_count: int


class FacetDto(BaseModel):
    id: str
    property_path: str
    name: str
    description: str | None
    is_static: bool
    is_lazy: bool = True
    type: FacetType


class CreateFacetDto(BaseModel):
    property_path: str
    name: str
    description: str | None

    @pydantic.validator("property_path")
    def name_validator(cls, v: str):
        if not v.strip():
            raise ValueError("property_path must not be empty")
        return v

    @pydantic.validator("name")
    def property_path_validator(cls, v: str):
        if not v.strip():
            raise ValueError("name must not be empty")
        return v
