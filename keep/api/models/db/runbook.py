from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, Column, TEXT, JSON
from sqlmodel import Field, Relationship, SQLModel
from keep.api.models.db.tenant import Tenant 

# Runbook Model
class Runbook(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    tenant: Tenant = Relationship()

    title: str = Field(nullable=False)  # Title of the runbook
    link: str = Field(nullable=False)   # Link to the .md file

    incidents: List["Incident"] = Relationship(
        back_populates="runbooks", link_model=RunbookToIncident
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True


# Link Model between Runbook and Incident
class RunbookToIncident(SQLModel, table=True):
    tenant_id: str = Field(foreign_key="tenant.id")
    runbook_id: UUID = Field(foreign_key="runbook.id", primary_key=True)
    incident_id: UUID = Field(foreign_key="incident.id", primary_key=True)

    incident_id: UUID = Field(
        sa_column=Column(
            UUID(binary=False),
            ForeignKey("incident.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )


# Incident Model
class Incident(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    tenant: Tenant = Relationship()

    user_generated_name: Optional[str] = None
    ai_generated_name: Optional[str] = None

    user_summary: Optional[str] = Field(sa_column=Column(TEXT), nullable=True)
    generated_summary: Optional[str] = Field(sa_column=Column(TEXT), nullable=True)

    assignee: Optional[str] = None
    severity: int = Field(default=IncidentSeverity.CRITICAL.order)

    creation_time: datetime = Field(default_factory=datetime.utcnow)

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    last_seen_time: Optional[datetime] = None

    runbooks: List["Runbook"] = Relationship(
        back_populates="incidents", link_model=RunbookToIncident
    )

    is_predicted: bool = Field(default=False)
    is_confirmed: bool = Field(default=False)

    alerts_count: int = Field(default=0)
    affected_services: List = Field(sa_column=Column(JSON), default_factory=list)
    sources: List = Field(sa_column=Column(JSON), default_factory=list)

    rule_id: Optional[UUID] = Field(
        sa_column=Column(
            UUID(binary=False),
            ForeignKey("rule.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    rule_fingerprint: str = Field(default="", sa_column=Column(TEXT))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if "runbooks" not in kwargs:
            self.runbooks = []

    class Config:
        arbitrary_types_allowed = True
