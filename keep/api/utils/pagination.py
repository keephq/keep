from typing import Any

from pydantic import BaseModel

from keep.api.models.alert import AlertDto, IncidentDto
from keep.api.models.db.workflow import *  # pylint: disable=unused-wildcard-importfrom typing import Optional
from keep.api.models.workflow import WorkflowDTO, WorkflowExecutionDTO


class PaginatedResultsDto(BaseModel):
    limit: int = 25
    offset: int = 0
    count: int
    items: list[Any]


class IncidentsPaginatedResultsDto(PaginatedResultsDto):
    items: list[IncidentDto]


class AlertPaginatedResultsDto(PaginatedResultsDto):
    items: list[AlertDto]


class WorkflowExecutionsPaginatedResultsDto(PaginatedResultsDto):
    items: list[WorkflowExecutionDTO]
    passCount: int = 0
    avgDuration: float = 0.0
    workflow: Optional[WorkflowDTO] = None
    failCount: int = 0
