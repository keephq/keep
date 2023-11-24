from datetime import datetime
from typing import List, Optional

from sqlalchemy import String
from sqlmodel import JSON, Column, Field, Relationship, SQLModel, UniqueConstraint


class Workflow(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    name: str
    description: Optional[str]
    created_by: str
    updated_by: Optional[str] = None
    creation_time: datetime = Field(default_factory=datetime.utcnow)
    interval: Optional[int]
    workflow_raw: str = Field(sa_column=String(length=65535))
    is_deleted: bool = Field(default=False)
    revision: int = Field(default=1, nullable=False)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True


class WorkflowExecution(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("workflow_id", "execution_number"),)

    id: str = Field(default=None, primary_key=True)
    workflow_id: str = Field(foreign_key="workflow.id")
    tenant_id: str = Field(foreign_key="tenant.id")
    started: datetime = Field(default_factory=datetime.utcnow)
    triggered_by: str
    status: str
    execution_number: int
    logs: Optional[str]
    error: Optional[str] = Field(sa_column=String(length=10240))
    execution_time: Optional[int]
    results: dict = Field(sa_column=Column(JSON), default={})

    logs: List["WorkflowExecutionLog"] = Relationship(
        back_populates="workflowexecution"
    )

    class Config:
        orm_mode = True


class WorkflowExecutionLog(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    workflow_execution_id: str = Field(foreign_key="workflowexecution.id")
    timestamp: datetime
    message: str
    workflowexecution: Optional[WorkflowExecution] = Relationship(back_populates="logs")
    context: dict = Field(sa_column=Column(JSON))

    class Config:
        orm_mode = True
