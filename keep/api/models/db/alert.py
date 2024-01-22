from datetime import datetime
from typing import List
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from keep.api.models.db.tenant import Tenant


# many to many map between alerts and groups
class AlertToGroup(SQLModel, table=True):
    tenant_id: str = Field(foreign_key="tenant.id")
    alert_id: UUID = Field(foreign_key="alert.id", primary_key=True)
    group_id: UUID = Field(foreign_key="group.id", primary_key=True)


class Group(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    rule_id: str = Field(foreign_key="rule.id")
    # the instance of the grouping criteria
    # e.g. grouping_criteria = ["event.labels.queue", "event.labels.cluster"] => group_fingerprint = "queue1,cluster1"
    group_fingerprint: str
    # map of attributes to values
    alerts: List["Alert"] = Relationship(
        back_populates="groups", link_model=AlertToGroup
    )


class Alert(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    tenant: Tenant = Relationship()
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    provider_type: str
    provider_id: str | None
    event: dict = Field(sa_column=Column(JSON))
    fingerprint: str = Field(index=True)  # Add the fingerprint field with an index
    groups: List["Group"] = Relationship(
        back_populates="alerts", link_model=AlertToGroup
    )

    # Define a one-to-one relationship to AlertEnrichment using alert_fingerprint
    alert_enrichment: "AlertEnrichment" = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "and_(Alert.fingerprint == foreign(AlertEnrichment.alert_fingerprint), Alert.tenant_id == AlertEnrichment.tenant_id)",
            "uselist": False,
        }
    )

    class Config:
        arbitrary_types_allowed = True


class AlertEnrichment(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    alert_fingerprint: str = Field(unique=True)
    enrichments: dict = Field(sa_column=Column(JSON))

    alerts: list[Alert] = Relationship(
        back_populates="alert_enrichment",
        sa_relationship_kwargs={
            "primaryjoin": "and_(Alert.fingerprint == AlertEnrichment.alert_fingerprint, Alert.tenant_id == AlertEnrichment.tenant_id)",
            "foreign_keys": "[AlertEnrichment.alert_fingerprint, AlertEnrichment.tenant_id]",
            "uselist": True,
        },
    )

    class Config:
        arbitrary_types_allowed = True


class AlertRaw(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    raw_alert: dict = Field(sa_column=Column(JSON))

    class Config:
        arbitrary_types_allowed = True
