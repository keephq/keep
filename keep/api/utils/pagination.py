from typing import Any

from pydantic import BaseModel

from keep.api.models.alert import IncidentDto, AlertDto


class PaginatedResultsDto(BaseModel):
    limit: int = 25
    offset: int = 0
    count: int
    items: list[Any]


class IncidentsPaginatedResultsDto(PaginatedResultsDto):
    items: list[IncidentDto]


class AlertPaginatedResultsDto(PaginatedResultsDto):
    items: list[AlertDto]
