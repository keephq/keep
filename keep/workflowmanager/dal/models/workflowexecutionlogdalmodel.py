from datetime import datetime
from pydantic import BaseModel


class WorkflowExecutioLogDalModel(BaseModel):
    id: int
    workflow_execution_id: str
    timestamp: datetime
    message: str
    context: dict
