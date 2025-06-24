from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from keep.workflowmanager.dal.models.workflowexecutiondalmodel import (
    WorkflowExecutionDalModel,
)


class WorkflowDalModel(BaseModel):
    id: str
    tenant_id: str
    name: Optional[str]
    description: Optional[str]
    created_by: Optional[str]
    updated_by: Optional[str] = None
    creation_time: Optional[datetime]
    interval: Optional[int]
    workflow_raw: Optional[str]
    is_deleted: Optional[bool] = False
    is_disabled: Optional[bool]
    revision: Optional[int] = 1
    last_updated: Optional[datetime]
    provisioned: Optional[bool]
    provisioned_file: Optional[str]
    is_test: Optional[bool]


class WorkflowWithLastExecutionsDalModel(WorkflowDalModel):
    workflow_last_run_started: Optional[datetime]
    workflow_last_run_time: Optional[datetime]
    workflow_last_run_status: Optional[str]
    workflow_last_executions: list[WorkflowExecutionDalModel] = []


class WorkflowVersionDalModel(BaseModel):
    workflow_id: Optional[str]
    tenant_id: Optional[str]
    revision: Optional[int]
    workflow_raw: Optional[str]
    updated_by: Optional[str]
    updated_at: Optional[datetime]
    is_valid: Optional[bool]
    is_current: Optional[bool]
    comment: Optional[str] = None
