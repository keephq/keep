import logging
from datetime import datetime
from typing import List
from uuid import UUID, uuid4

from pydantic import PrivateAttr
from sqlalchemy import ForeignKey, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy_utils import UUIDType
from sqlmodel import JSON, TEXT, Column, Field, Index, Relationship, SQLModel

from keep.api.core.config import config
from keep.api.models.db.helpers import DATETIME_COLUMN_TYPE, NULL_FOR_DELETED_AT
from keep.api.models.db.incident import Incident
from keep.api.models.db.tenant import Tenant

db_connection_string = config("DATABASE_CONNECTION_STRING", default=None)
logger = logging.getLogger(__name__)


class AlertToIncident(SQLModel, table=True):
    tenant_id: str = Field(foreign_key="tenant.id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    alert_id: UUID = Field(foreign_key="alert.id", primary_key=True)
    incident_id: UUID = Field(
        sa_column=Column(
            UUIDType(binary=False),
            ForeignKey("incident.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )

    is_created_by_ai: bool = Field(default=False)

    deleted_at: datetime = Field(
        default_factory=None,
        nullable=True,
        primary_key=True,
        default=NULL_FOR_DELETED_AT,
    )


class LastAlert(SQLModel, table=True):

    tenant_id: str = Field(foreign_key="tenant.id", nullable=False, primary_key=True)
    fingerprint: str = Field(primary_key=True, index=True)
    alert_id: UUID = Field(foreign_key="alert.id")
    timestamp: datetime = Field(nullable=False, index=True)
    first_timestamp: datetime = Field(nullable=False, index=True)
    alert_hash: str | None = Field(nullable=True, index=True)

    __table_args__ = (
        # Original indexes from MySQL
        Index("idx_lastalert_tenant_timestamp", "tenant_id", "first_timestamp"),
        Index("idx_lastalert_tenant_timestamp_new", "tenant_id", "timestamp"),
        Index(
            "idx_lastalert_tenant_ordering",
            "tenant_id",
            "first_timestamp",
            "alert_id",
            "fingerprint",
        ),
        {},
    )


class LastAlertToIncident(SQLModel, table=True):
    tenant_id: str = Field(foreign_key="tenant.id", nullable=False, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    fingerprint: str = Field(primary_key=True)
    incident_id: UUID = Field(
        sa_column=Column(
            UUIDType(binary=False),
            ForeignKey("incident.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )

    is_created_by_ai: bool = Field(default=False)

    deleted_at: datetime = Field(
        default_factory=None,
        nullable=True,
        primary_key=True,
        default=NULL_FOR_DELETED_AT,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "fingerprint"],
            ["lastalert.tenant_id", "lastalert.fingerprint"],
        ),
        Index(
            "idx_lastalerttoincident_tenant_fingerprint",
            "tenant_id",
            "fingerprint",
            "deleted_at",
        ),
        Index(
            "idx_tenant_deleted_fingerprint", "tenant_id", "deleted_at", "fingerprint"
        ),
        {},
    )


class Alert(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    tenant: Tenant = Relationship()
    # index=True added because we query top 1000 alerts order by timestamp.
    # On a large dataset, this will be slow without an index.
    #            with 1M alerts, we see queries goes from >30s to 0s with the index
    #            todo: on MSSQL, the index is "nonclustered" index which cannot be controlled by SQLModel
    timestamp: datetime = Field(
        sa_column=Column(DATETIME_COLUMN_TYPE, index=True, nullable=False),
        default_factory=lambda: datetime.utcnow().replace(
            microsecond=int(datetime.utcnow().microsecond / 1000) * 1000
        ),
    )
    provider_type: str
    provider_id: str | None
    event: dict = Field(sa_column=Column(JSON))
    fingerprint: str = Field(index=True)  # Add the fingerprint field with an index

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

    alert_instance_enrichment: "AlertEnrichment" = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "and_(cast(Alert.id, String) == foreign(AlertEnrichment.alert_fingerprint), Alert.tenant_id == AlertEnrichment.tenant_id)",
            "uselist": False,
            "viewonly": True,
        },
    )

    _incidents: List[Incident] = PrivateAttr(default_factory=list)

    __table_args__ = (
        Index(
            "ix_alert_tenant_fingerprint_timestamp",
            "tenant_id",
            "fingerprint",
            "timestamp",
        ),
        Index("idx_fingerprint_timestamp", "fingerprint", "timestamp"),
        Index(
            "idx_alert_tenant_timestamp_fingerprint",
            "tenant_id",
            "timestamp",
            "fingerprint",
        ),
        # Index to optimize linked provider queries (is_linked_provider function)
        # These queries look for alerts with specific tenant_id and provider_id combinations
        # where the provider doesn't exist in the provider table
        # Without this index, the query scans 400k+ rows and takes ~2s
        # With this index, the query takes ~0.4s
        Index(
            "idx_alert_tenant_provider",
            "tenant_id",
            "provider_id",
        ),
    )

    class Config:
        arbitrary_types_allowed = True


class AlertEnrichment(SQLModel, table=True):
    """
    TODO: we need to rename this table to EntityEnrichment since it's not only for alerts anymore.
    @tb: for example, we use it also for Incidents now.
    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    alert_fingerprint: str = Field(unique=True)
    enrichments: dict = Field(sa_column=Column(JSON))

    # @tb: we need to think what to do about this relationship.
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


class AlertDeduplicationRule(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    name: str = Field(index=True)
    description: str
    provider_id: str | None = Field(default=None)  # None for default rules
    provider_type: str
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    last_updated_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str
    enabled: bool = Field(default=True)
    fingerprint_fields: list[str] = Field(sa_column=Column(JSON), default=[])
    full_deduplication: bool = Field(default=False)
    ignore_fields: list[str] = Field(sa_column=Column(JSON), default=[])
    priority: int = Field(default=0)  # for future use
    is_provisioned: bool = Field(default=False)

    class Config:
        arbitrary_types_allowed = True


class AlertDeduplicationEvent(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id", index=True)
    timestamp: datetime = Field(
        sa_column=Column(DATETIME_COLUMN_TYPE, nullable=False),
        default_factory=datetime.utcnow,
    )
    deduplication_rule_id: UUID  # TODO: currently rules can also be implicit (like default) so they won't exists on db Field(foreign_key="alertdeduplicationrule.id", index=True)
    deduplication_type: str = Field()  # 'full' or 'partial'
    date_hour: datetime = Field(
        sa_column=Column(DATETIME_COLUMN_TYPE),
        default_factory=lambda: datetime.utcnow().replace(
            minute=0, second=0, microsecond=0
        ),
    )
    # these are only soft reference since it could be linked provider
    provider_id: str | None = Field()
    provider_type: str | None = Field()

    __table_args__ = (
        Index(
            "ix_alert_deduplication_event_provider_id",
            "provider_id",
        ),
        Index(
            "ix_alert_deduplication_event_provider_type",
            "provider_type",
        ),
        Index(
            "ix_alert_deduplication_event_provider_id_date_hour",
            "provider_id",
            "date_hour",
        ),
        Index(
            "ix_alert_deduplication_event_provider_type_date_hour",
            "provider_type",
            "date_hour",
        ),
    )

    class Config:
        arbitrary_types_allowed = True


class AlertField(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id", index=True)
    field_name: str = Field(index=True)
    provider_id: str | None = Field(index=True)
    provider_type: str | None = Field(index=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "field_name", name="uq_tenant_field"),
        Index("ix_alert_field_tenant_id", "tenant_id"),
        Index("ix_alert_field_tenant_id_field_name", "tenant_id", "field_name"),
        Index(
            "ix_alert_field_provider_id_provider_type", "provider_id", "provider_type"
        ),
    )

    class Config:
        arbitrary_types_allowed = True


class AlertRaw(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id", index=True)
    raw_alert: dict = Field(sa_column=Column(JSON))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    provider_type: str | None = Field(default=None)
    error: bool = Field(default=False, index=True)
    error_message: str | None = Field(default=None)
    dismissed: bool = Field(default=False)
    dismissed_at: datetime | None = Field(default=None)
    dismissed_by: str | None = Field(default=None)

    __table_args__ = (
        Index("ix_alert_raw_tenant_id_error", "tenant_id", "error"),
        Index("ix_alert_raw_tenant_id_timestamp", "tenant_id", "timestamp"),
    )

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
    description: str = Field(sa_column=Column(TEXT))

    __table_args__ = (
        Index("ix_alert_audit_tenant_id", "tenant_id"),
        Index("ix_alert_audit_fingerprint", "fingerprint"),
        Index("ix_alert_audit_tenant_id_fingerprint", "tenant_id", "fingerprint"),
        Index("ix_alert_audit_timestamp", "timestamp"),
    )
