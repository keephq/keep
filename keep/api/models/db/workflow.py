from datetime import datetime
from typing import Optional

from sqlmodel import Field, ForeignKey, SQLModel


class Workflow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str
    created_by: str
    last_execution: Optional[datetime]
    path: str

    class Config:
        orm_mode = True


class WorkflowExecution(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="workflow.id")
    started: datetime = Field(default_factory=datetime.utcnow)
    triggered_by: str
    status: str
    logs: List[str] = []
    error: Optional[str]
    execution_time: Optional[int]

    class Config:
        orm_mode = True
