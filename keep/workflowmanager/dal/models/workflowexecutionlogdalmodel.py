from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class WorkflowExecutioLogDalModel(BaseModel):
    id: Optional[str] = None
    workflow_execution_id: Optional[str]
    timestamp: Optional[datetime]
    message: Optional[str]
    context: Optional[dict]
