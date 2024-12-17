from datetime import datetime
from typing import List, Optional

from sqlalchemy import TEXT, Index
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
    is_disabled: bool = Field(default=False)
    revision: int = Field(default=1, nullable=False)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    provisioned: bool = Field(default=False)
    provisioned_file: Optional[str] = None

    class Config:
        orm_mode = True


class WorkflowExecution(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("workflow_id", "execution_number", "is_running", "timeslot"),
        Index(
            "idx_workflowexecution_tenant_workflow_id_timestamp",
            "tenant_id",
            "workflow_id",
            "started",
        ),
    )

    id: str = Field(default=None, primary_key=True)
    workflow_id: str = Field(foreign_key="workflow.id")
    tenant_id: str = Field(foreign_key="tenant.id")
    started: datetime = Field(default_factory=datetime.utcnow)
    triggered_by: str = Field(sa_column=Column(TEXT))
    status: str = Field(sa_column=Column(TEXT))
    is_running: int = Field(default=1)
    timeslot: int = Field(
        default_factory=lambda: int(datetime.utcnow().timestamp() / 120)
    )
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
    workflow_to_incident_execution: "WorkflowToIncidentExecution" = Relationship(
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
    event_id: str | None
    workflow_execution: WorkflowExecution = Relationship(
        back_populates="workflow_to_alert_execution"
    )


class WorkflowToIncidentExecution(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("workflow_execution_id", "incident_id"),)

    # https://sqlmodel.tiangolo.com/tutorial/automatic-id-none-refresh/
    id: Optional[int] = Field(primary_key=True, default=None)
    workflow_execution_id: str = Field(foreign_key="workflowexecution.id")
    incident_id: str | None
    workflow_execution: WorkflowExecution = Relationship(
        back_populates="workflow_to_incident_execution"
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
