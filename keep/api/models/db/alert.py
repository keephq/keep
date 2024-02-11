import hashlib
from datetime import datetime
from typing import List
from uuid import uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from keep.api.models.db.tenant import Tenant


# many to many map between alerts and groups
class AlertToGroup(SQLModel, table=True):
    tenant_id: str = Field(foreign_key="tenant.id", max_length=36)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    alert_id: str = Field(foreign_key="alert.id", primary_key=True, max_length=36)
    group_id: str = Field(foreign_key="group.id", primary_key=True, max_length=36)


class Group(SQLModel, table=True):
    id: str = Field(
        default_factory=lambda: str(uuid4()), primary_key=True, max_length=36
    )
    tenant_id: str = Field(foreign_key="tenant.id", max_length=36)
    rule_id: str = Field(foreign_key="rule.id", max_length=36)
    creation_time: datetime = Field(default_factory=datetime.utcnow)
    # the instance of the grouping criteria
    # e.g. grouping_criteria = ["event.labels.queue", "event.labels.cluster"] => group_fingerprint = "queue1,cluster1"

    # Note: IT IS NOT A UNIQUE IDENTIFIER (as in alerts)
    group_fingerprint: str
    # map of attributes to values
    alerts: List["Alert"] = Relationship(
        back_populates="groups", link_model=AlertToGroup
    )

    def calculate_fingerprint(self):
        return hashlib.sha256(
            "|".join([str(self.id), self.group_fingerprint]).encode()
        ).hexdigest()


class Alert(SQLModel, table=True):
    id: str = Field(
        default_factory=lambda: str(uuid4()), primary_key=True, max_length=36
    )
    tenant_id: str = Field(foreign_key="tenant.id", max_length=36)
    tenant: Tenant = Relationship()
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    provider_type: str
    provider_id: str | None
    event: dict = Field(sa_column=Column(JSON))
    fingerprint: str = Field(
        index=True, max_length=256
    )  # Add the fingerprint field with an index
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
    id: str = Field(
        default_factory=lambda: str(uuid4()), primary_key=True, max_length=36
    )
    tenant_id: str = Field(foreign_key="tenant.id", max_length=36)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    alert_fingerprint: str = Field(unique=True, max_length=256)
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
    id: str = Field(
        default_factory=lambda: str(uuid4()), primary_key=True, max_length=36
    )
    tenant_id: str = Field(foreign_key="tenant.id", max_length=36)
    raw_alert: dict = Field(sa_column=Column(JSON))

    class Config:
        arbitrary_types_allowed = True
