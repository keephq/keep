from datetime import datetime
from typing import List, Optional

from sqlalchemy import TEXT
from sqlmodel import JSON, Column, Field, Relationship, SQLModel, UniqueConstraint


class Workflow(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    name: str = Field(sa_column=Column(TEXT))
    description: Optional[str]
    created_by: str = Field(sa_column=Column(TEXT))
    updated_by: Optional[str] = None
    creation_time: datetime = Field(default_factory=datetime.utcnow)
    interval: Optional[int]
    workflow_raw: str = Field(sa_column=Column(TEXT))
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
    triggered_by: str = Field(sa_column=Column(TEXT))
    status: str = Field(sa_column=Column(TEXT))
    execution_number: int
    logs: Optional[str]
    error: Optional[str] = Field(max_length=10240)
    execution_time: Optional[int]
    results: dict = Field(sa_column=Column(JSON), default={})

    logs: List["WorkflowExecutionLog"] = Relationship(
        back_populates="workflowexecution"
    )
    workflow_to_alert_execution: "WorkflowToAlertExecution" = Relationship(
        back_populates="workflow_execution"
    )

    class Config:
        orm_mode = True


class WorkflowToAlertExecution(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("workflow_execution_id", "alert_fingerprint"),)

    # https://sqlmodel.tiangolo.com/tutorial/automatic-id-none-refresh/
    id: Optional[int] = Field(primary_key=True, default=None)
    workflow_execution_id: str = Field(foreign_key="workflowexecution.id")
    alert_fingerprint: str
    event_id: str
    workflow_execution: WorkflowExecution = Relationship(
        back_populates="workflow_to_alert_execution"
    )


class WorkflowExecutionLog(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    workflow_execution_id: str = Field(foreign_key="workflowexecution.id")
    timestamp: datetime
    message: str = Field(sa_column=Column(TEXT))
    workflowexecution: Optional[WorkflowExecution] = Relationship(back_populates="logs")
    context: dict = Field(sa_column=Column(JSON))

    class Config:
        orm_mode = True
