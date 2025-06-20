from datetime import datetime
from typing import Optional, TypedDict
from pydantic import BaseModel

from keep.workflowmanager.dal.models.workflowexecutiondalmodel import (
    WorkflowExecutionDalModel,
)


class WorkflowDalModel(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: Optional[str]
    created_by: str
    updated_by: Optional[str] = None
    creation_time: datetime
    interval: Optional[int]
    workflow_raw: str
    is_deleted: bool = False
    is_disabled: bool
    revision: int = 1
    last_updated: datetime
    provisioned: bool
    provisioned_file: Optional[str]
    is_test: bool


class WorkflowWithLastExecutionsDalModel(WorkflowDalModel):
    workflow_last_run_started: Optional[datetime]
    workflow_last_run_time: Optional[datetime]
    workflow_last_run_status: Optional[str]
    workflow_last_executions: list[WorkflowExecutionDalModel] = []
