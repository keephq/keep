from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class WorkflowExecutionDalModel(BaseModel):
    id: str
    workflow_id: str
    workflow_revision: int
    tenant_id: str
    started: datetime
    triggered_by: str
    status: str
    is_running: int
    timeslot: int
    execution_number: int
    error: Optional[str]
    execution_time: Optional[int]
    results: dict
    is_test_run: bool

    class Config:
        use_enum_values = True
