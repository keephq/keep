from datetime import datetime
from typing import List, Optional

from sqlalchemy import TEXT, DateTime, Index, PrimaryKeyConstraint, func
from sqlmodel import JSON, Column, Field, Relationship, SQLModel, UniqueConstraint


def get_dummy_workflow_id(tenant_id: str) -> str:
    return f"system-dummy-workflow-{tenant_id}"


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
    last_updated: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            name="last_updated",
            onupdate=func.now(),
            server_default=func.now(),
            nullable=False,
        )
    )
    provisioned: bool = Field(default=False)
    provisioned_file: Optional[str] = None
    is_test: bool = Field(default=False)

    executions: List["WorkflowExecution"] = Relationship(back_populates="workflow")
    versions: List["WorkflowVersion"] = Relationship(back_populates="workflow")

    class Config:
        orm_mode = True


class WorkflowVersion(SQLModel, table=True):
    __table_args__ = (PrimaryKeyConstraint("workflow_id", "revision"),)

    workflow_id: str = Field(primary_key=True, foreign_key="workflow.id")
    revision: int = Field(primary_key=True)
    workflow_raw: str = Field(sa_column=Column(TEXT))
    updated_by: str
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            name="updated_at",
            onupdate=func.now(),
            server_default=func.now(),
            nullable=False,
        )
    )
    is_valid: bool = Field(default=False)
    is_current: bool = Field(default=False)
    comment: Optional[str] = None

    workflow: "Workflow" = Relationship(back_populates="versions")
    executions: List["WorkflowExecution"] = Relationship(
        back_populates="version",
        sa_relationship_kwargs={
            "primaryjoin": "and_(WorkflowVersion.workflow_id == WorkflowExecution.workflow_id, "
            "WorkflowVersion.revision == WorkflowExecution.workflow_revision)",
            "foreign_keys": "[WorkflowExecution.workflow_id, WorkflowExecution.workflow_revision]",
            "viewonly": True,
        },
    )


class WorkflowExecution(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("workflow_id", "execution_number", "is_running", "timeslot"),
        Index(
            "idx_workflowexecution_tenant_workflow_id_timestamp",
            "tenant_id",
            "workflow_id",
            "started",
        ),
        Index(
            "idx_workflowexecution_tenant_workflow_id_revision_timestamp",
            "tenant_id",
            "workflow_id",
            "workflow_revision",
            "started",
        ),
        Index(
            "idx_workflowexecution_workflow_tenant_started_status",
            "workflow_id",
            "tenant_id",
            "started",
            "status",
            mysql_length={"status": 255},
        ),
        Index(
            "idx_workflowexecution_workflow_revision_tenant_started_status",
            "workflow_id",
            "workflow_revision",
            "tenant_id",
            "started",
            "status",
            mysql_length={"status": 255},
        ),
        Index(
            "idx_status_started",
            "status",
            "started",
            mysql_length={"status": 255},
        ),
        Index(
            "idx_workflowexecution_workflow_revision",
            "workflow_id",
            "workflow_revision",
        ),
    )

    id: str = Field(default=None, primary_key=True)
    workflow_id: str = Field(
        foreign_key="workflow.id", default="test"
    )  # default=test for test runs, which are not associated with a workflow
    workflow_revision: int = Field(
        default=1
    )  # Add this to track which version was executed
    tenant_id: str = Field(foreign_key="tenant.id")
    started: datetime = Field(default_factory=datetime.utcnow, index=True)
    triggered_by: str = Field(sa_column=Column(TEXT))
    status: str = Field(sa_column=Column(TEXT))
    is_running: int = Field(default=1)
    timeslot: int = Field(
        default_factory=lambda: int(datetime.utcnow().timestamp() / 120)
    )
    execution_number: int
    error: Optional[str] = Field(max_length=10240)
    execution_time: Optional[int]
    results: dict = Field(sa_column=Column(JSON), default={})
    is_test_run: bool = Field(default=False)

    workflow: "Workflow" = Relationship(
        back_populates="executions",
        sa_relationship_kwargs={"foreign_keys": "[WorkflowExecution.workflow_id]"},
    )

    version: "WorkflowVersion" = Relationship(
        back_populates="executions",
        sa_relationship_kwargs={
            "primaryjoin": "and_(WorkflowVersion.workflow_id == WorkflowExecution.workflow_id, WorkflowVersion.revision == WorkflowExecution.workflow_revision)",
            "foreign_keys": "[WorkflowExecution.workflow_id, WorkflowExecution.workflow_revision]",
            "viewonly": True,
        },
    )

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
