from typing import Any

from pydantic import BaseModel

from keep.api.models.alert import IncidentDto, AlertDto 
from keep.api.models.workflow import (
    WorkflowExecutionDTO,
)
from keep.api.models.db.workflow import *  # pylint: disable=unused-wildcard-import
from typing import Optional


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
    passFail: float = 0.0
    avgDuration: float = 0.0
    workflow: Optional[Workflow] = None
