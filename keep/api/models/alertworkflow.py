from typing import List, Optional

from pydantic import BaseModel


class WorkflowProvider(BaseModel):
    provider_id: str
    provider_type: str
    config: dict


class WorkflowCondition(BaseModel):
    name: str
    type: str
    value: str
    compare_to: str


class WorkflowStep(BaseModel):
    name: str
    provider: WorkflowProvider
    condition: Optional[List[WorkflowCondition]]


class WorkflowDTO(BaseModel):
    id: str
    description: Optional[str] = None
    owners: List[str]
    interval: int
    steps: List[WorkflowStep]
    actions: List[WorkflowStep]
