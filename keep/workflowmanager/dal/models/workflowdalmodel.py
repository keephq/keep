from datetime import datetime
from typing import Optional
from pydantic import BaseModel


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
    is_deleted: bool
    is_disabled: bool
    revision: int
    last_updated: datetime
    provisioned: bool
    provisioned_file: Optional[str]
    is_test: bool
