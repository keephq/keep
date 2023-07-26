from typing import List, Optional

from pydantic import BaseModel


class WorkflowStepProvider(BaseModel):
    type: str
    config: str
    with_: dict


class WorkflowStep(BaseModel):
    name: str
    provider: WorkflowStepProvider


class WorkflowCondition(BaseModel):
    name: str
    type: str
    value: str
    compare_to: str


class WorkflowActionProvider(BaseModel):
    type: str
    config: str
    with_: dict


class WorkflowAction(BaseModel):
    name: str
    condition: List[WorkflowCondition]
    provider: WorkflowActionProvider


class WorkflowDTO(BaseModel):
    id: str
    description: str
    owners: List[str]
    services: List[str]
    interval: int
    steps: List[WorkflowStep]
    actions: List[WorkflowAction]


class Providers(BaseModel):
    description: str
    authentication: dict
    # Add more fields as needed


class WorkflowConfig(BaseModel):
    alert: WorkflowDTO
    providers: dict[str, Providers]
