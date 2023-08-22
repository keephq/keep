from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ProviderDTO(BaseModel):
    type: str
    id: str | None  # if not installed - no id
    name: str
    installed: bool


class WorkflowDTO(BaseModel):
    id: str
    description: Optional[str] = None
    created_by: str
    creation_time: datetime
    triggers: List[str] = None
    interval: int
    providers: List[ProviderDTO]


class WorkflowExecutionDTO(BaseModel):
    id: str
    workflow_id: str
    started: datetime
    triggered_by: str
    status: str
    logs: Optional[str]
    error: Optional[str]
    execution_time: Optional[int]
