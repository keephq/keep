from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, ForeignKey, SQLModel


class Workflow(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    name: str
    description: str
    created_by: str
    creation_time: datetime = Field(default_factory=datetime.utcnow)
    interval: Optional[int]
    workflow_raw: str = Field(sql_type="TEXT")

    class Config:
        orm_mode = True


class WorkflowExecution(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    workflow_id: str = Field(foreign_key="workflow.id")
    tenant_id: str = Field(foreign_key="tenant.id")
    started: datetime = Field(default_factory=datetime.utcnow)
    triggered_by: str
    status: str
    logs: Optional[str]
    error: Optional[str]
    execution_time: Optional[int]

    class Config:
        orm_mode = True
