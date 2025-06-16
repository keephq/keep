from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class WorkflowExecutionDalModel(BaseModel):
    id: str
    workflow_id: Optional[str]
    tenant_id: Optional[str]
    workflow_revision: Optional[int] = None
    started: Optional[datetime] = None
    triggered_by: Optional[str] = None
    status: Optional[str] = None
    is_running: Optional[int] = None
    timeslot: Optional[int] = None
    execution_number: Optional[int] = None
    error: Optional[str] = None
    execution_time: Optional[int] = None
    results: Optional[dict] = None
    is_test_run: Optional[bool] = None
    event_type: Optional[str]
    event_id: Optional[str]

    class Config:
        use_enum_values = True
