from typing import Any, Optional
from pydantic import BaseModel

from keep.api.models.db.facet import FacetType

class FacetOptionDto(BaseModel):
    display_name: str
    value: Any
    matches_count: int

class FacetDto(BaseModel):
    id: str
    property_path: str
    name: str
    description: Optional[str]
    is_static: bool
    is_lazy: bool = True
    type: FacetType

class CreateFacetDto(BaseModel):
    property_path: str
    name: str
    description: Optional[str]
