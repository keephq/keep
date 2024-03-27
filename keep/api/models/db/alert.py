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
    # index=True added because we query top 1000 alerts order by timestamp. On a large dataset, this will be slow without an index.
    #            with 1M alerts, we see queries goes from >30s to 0s with the index
    #            todo: on MSSQL, the index is "nonclustered" index which cannot be controlled by SQLModel
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    provider_type: str
    provider_id: str | None
    event: dict = Field(sa_column=Column(JSON))
    fingerprint: str = Field(
        index=True, max_length=256
    )  # Add the fingerprint field with an index
    groups: List["Group"] = Relationship(
        back_populates="alerts", link_model=AlertToGroup
    )
    # alert_hash is different than fingerprint, it is a hash of the alert itself
    #            and it is used for deduplication.
    #            alert can be different but have the same fingerprint (e.g. different "firing" and "resolved" will have the same fingerprint but not the same alert_hash)
    alert_hash: str | None

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


class AlertDeduplicationFilter(SQLModel, table=True):
    id: str = Field(
        default_factory=lambda: str(uuid4()), primary_key=True, max_length=36
    )
    tenant_id: str = Field(foreign_key="tenant.id", max_length=36)
    # the list of fields to pop from the alert before hashing
    fields: list = Field(sa_column=Column(JSON), default=[])
    # a CEL expression to match the alert
    matcher_cel: str = Field(max_length=2000)

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
