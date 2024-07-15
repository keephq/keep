import enum
import hashlib
import logging
from datetime import datetime
from typing import List
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.mssql import DATETIME2 as MSSQL_DATETIME2
from sqlalchemy.dialects.mysql import DATETIME as MySQL_DATETIME
from sqlalchemy.engine.url import make_url
from sqlalchemy_utils import UUIDType
from sqlmodel import JSON, Column, DateTime, Field, Index, Relationship, SQLModel

from keep.api.consts import RUNNING_IN_CLOUD_RUN
from keep.api.core.config import config
from keep.api.models.db.tenant import Tenant

db_connection_string = config("DATABASE_CONNECTION_STRING", default=None)
logger = logging.getLogger(__name__)
# managed (mysql)
if RUNNING_IN_CLOUD_RUN or db_connection_string == "impersonate":
    # Millisecond precision
    datetime_column_type = MySQL_DATETIME(fsp=3)
# self hosted (mysql, sql server, sqlite / postgres)
else:
    try:
        url = make_url(db_connection_string)
        dialect = url.get_dialect().name
        if dialect == "mssql":
            # Millisecond precision
            datetime_column_type = MSSQL_DATETIME2(precision=3)
        elif dialect == "mysql":
            # Millisecond precision
            datetime_column_type = MySQL_DATETIME(fsp=3)
        else:
            datetime_column_type = DateTime
    except Exception:
        logger.warning(
            "Could not determine the database dialect, falling back to default datetime column type"
        )
        # give it a default
        datetime_column_type = DateTime


# many to many map between alerts and groups
class AlertToGroup(SQLModel, table=True):
    tenant_id: str = Field(foreign_key="tenant.id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    alert_id: UUID = Field(foreign_key="alert.id", primary_key=True)
    group_id: UUID = Field(
        sa_column=Column(
            UUIDType(binary=False),
            ForeignKey("group.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )


class Group(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    rule_id: UUID = Field(
        sa_column=Column(
            UUIDType(binary=False), ForeignKey("rule.id", ondelete="CASCADE")
        ),
    )
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
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    tenant: Tenant = Relationship()
    # index=True added because we query top 1000 alerts order by timestamp. On a large dataset, this will be slow without an index.
    #            with 1M alerts, we see queries goes from >30s to 0s with the index
    #            todo: on MSSQL, the index is "nonclustered" index which cannot be controlled by SQLModel
    timestamp: datetime = Field(
        sa_column=Column(datetime_column_type, index=True, nullable=False),
        default_factory=lambda: datetime.utcnow().replace(
            microsecond=int(datetime.utcnow().microsecond / 1000) * 1000
        ),
    )
    provider_type: str
    provider_id: str | None
    event: dict = Field(sa_column=Column(JSON))
    fingerprint: str = Field(index=True)  # Add the fingerprint field with an index
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


class AlertDeduplicationFilter(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    # the list of fields to pop from the alert before hashing
    fields: list = Field(sa_column=Column(JSON), default=[])
    # a CEL expression to match the alert
    matcher_cel: str

    class Config:
        arbitrary_types_allowed = True


class AlertRaw(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    raw_alert: dict = Field(sa_column=Column(JSON))

    class Config:
        arbitrary_types_allowed = True


class AlertAudit(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    fingerprint: str
    tenant_id: str = Field(foreign_key="tenant.id", nullable=False)
    # when
    timestamp: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    # who
    user_id: str = Field(nullable=False)
    # what
    action: str = Field(nullable=False)
    description: str

    __table_args__ = (
        Index("ix_alert_audit_tenant_id", "tenant_id"),
        Index("ix_alert_audit_fingerprint", "fingerprint"),
        Index("ix_alert_audit_tenant_id_fingerprint", "tenant_id", "fingerprint"),
        Index("ix_alert_audit_timestamp", "timestamp"),
    )


class AlertActionType(enum.Enum):
    # the alert was triggered
    TIGGERED = "alert was triggered"
    # someone acknowledged the alert
    ACKNOWLEDGE = "alert acknowledged"
    # the alert was resolved
    AUTOMATIC_RESOLVE = "alert automatically resolved"
    # the alert was resolved manually
    MANUAL_RESOLVE = "alert manually resolved"
    MANUAL_STATUS_CHANGE = "alert status manually changed"
    # the alert was escalated
    WORKFLOW_ENRICH = "alert enriched by workflow"
    MAPPING_RULE_ENRICH = "alert enriched by mapping rule"
    # the alert was deduplicated
    DEDUPLICATED = "alert was deduplicated"
    # a ticket was created
    TICKET_ASSIGNED = "alert was assigned with ticket"
    # a ticket was updated
    TICKET_UPDATED = "alert ticket was updated"
    # disposing enriched alert
    DISPOSE_ENRICHED_ALERT = "alert enrichments disposed"
    # delete alert
    DELETE_ALERT = "alert deleted"
    # generic enrichment
    GENERIC_ENRICH = "alert enriched"
    # commented
    COMMENT = "a comment was added to the alert"
