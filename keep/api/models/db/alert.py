from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy import JSON as SAJSON
from sqlalchemy import Text as SAText
from sqlmodel import Field, Relationship, SQLModel

logger = logging.getLogger(__name__)


# -----------------------------
# Time helpers
# -----------------------------

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# -----------------------------
# Escalation domain
# -----------------------------

class EscalationChannel(str, Enum):
    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"
    PAGER = "pager"         # generic: pagerduty/opsgenie/etc.
    INTERNAL = "internal"   # internal queue or UI inbox


class EscalationStatus(str, Enum):
    OPEN = "open"
    ACKED = "acked"
    RESOLVED = "resolved"
    SILENCED = "silenced"
    FAILED = "failed"


class OutboxStatus(str, Enum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    DEAD = "dead"


# -----------------------------
# Base alert model (tightened)
# -----------------------------

class Alert(SQLModel, table=True):
    __tablename__ = "alert"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: str = Field(foreign_key="tenant.id", nullable=False, index=True, max_length=64)

    # Use real UTC timestamps with TZ
    timestamp: datetime = Field(
        default_factory=utcnow,
        nullable=False,
        index=True,
    )

    provider_type: str = Field(nullable=False, max_length=64)
    provider_id: Optional[str] = Field(default=None, index=True, max_length=128)

    # JSON event payload
    event: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(SAJSON, nullable=False),
    )

    fingerprint: str = Field(nullable=False, index=True, max_length=256)
    alert_hash: Optional[str] = Field(default=None, index=True, max_length=128)

    # Escalation state (one-to-one)
    escalation_state: Optional["AlertEscalationState"] = Relationship(
        back_populates="alert",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"},
    )

    __table_args__ = (
        Index("ix_alert_tenant_fingerprint_ts", "tenant_id", "fingerprint", "timestamp"),
        Index("ix_alert_tenant_ts_fingerprint", "tenant_id", "timestamp", "fingerprint"),
        Index("ix_alert_tenant_provider", "tenant_id", "provider_id"),
    )


# -----------------------------
# Enrichment (tenant-scoped uniqueness)
# -----------------------------

class AlertEnrichment(SQLModel, table=True):
    __tablename__ = "alert_enrichment"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: str = Field(foreign_key="tenant.id", nullable=False, index=True, max_length=64)

    timestamp: datetime = Field(default_factory=utcnow, nullable=False, index=True)

    # Was globally unique. That's wrong in multi-tenant.
    alert_fingerprint: str = Field(nullable=False, max_length=256)

    enrichments: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(SAJSON, nullable=False),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "alert_fingerprint", name="uq_enrich_tenant_fingerprint"),
        Index("ix_enrich_tenant_fingerprint", "tenant_id", "alert_fingerprint"),
    )


# -----------------------------
# Linking alerts to incidents (soft delete fixed)
# -----------------------------

class AlertToIncident(SQLModel, table=True):
    __tablename__ = "alert_to_incident"

    tenant_id: str = Field(foreign_key="tenant.id", nullable=False, index=True, max_length=64)

    alert_id: UUID = Field(foreign_key="alert.id", primary_key=True)
    incident_id: UUID = Field(
        sa_column=Column(
            ForeignKey("incident.id", ondelete="CASCADE"),
            nullable=False,
            primary_key=True,
        )
    )

    timestamp: datetime = Field(default_factory=utcnow, nullable=False, index=True)
    is_created_by_ai: bool = Field(default=False, nullable=False)

    # Proper soft delete
    deleted_at: Optional[datetime] = Field(default=None, nullable=True, index=True)

    __table_args__ = (
        Index("ix_a2i_tenant_deleted", "tenant_id", "deleted_at"),
    )


# -----------------------------
# LastAlert / LastAlertToIncident (timestamps fixed)
# -----------------------------

class LastAlert(SQLModel, table=True):
    __tablename__ = "last_alert"

    tenant_id: str = Field(foreign_key="tenant.id", nullable=False, primary_key=True, max_length=64)
    fingerprint: str = Field(primary_key=True, index=True, max_length=256)

    alert_id: UUID = Field(foreign_key="alert.id", nullable=False, index=True)
    timestamp: datetime = Field(nullable=False, index=True)
    first_timestamp: datetime = Field(nullable=False, index=True)
    alert_hash: Optional[str] = Field(default=None, index=True, max_length=128)

    __table_args__ = (
        Index("ix_lastalert_tenant_first_ts", "tenant_id", "first_timestamp"),
        Index("ix_lastalert_tenant_ts", "tenant_id", "timestamp"),
        Index("ix_lastalert_ordering", "tenant_id", "first_timestamp", "alert_id", "fingerprint"),
    )


class LastAlertToIncident(SQLModel, table=True):
    __tablename__ = "last_alert_to_incident"

    tenant_id: str = Field(foreign_key="tenant.id", nullable=False, primary_key=True, max_length=64)
    fingerprint: str = Field(primary_key=True, max_length=256)

    incident_id: UUID = Field(
        sa_column=Column(
            ForeignKey("incident.id", ondelete="CASCADE"),
            nullable=False,
            primary_key=True,
        )
    )

    timestamp: datetime = Field(default_factory=utcnow, nullable=False, index=True)
    is_created_by_ai: bool = Field(default=False, nullable=False)

    deleted_at: Optional[datetime] = Field(default=None, nullable=True, index=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "fingerprint"],
            ["last_alert.tenant_id", "last_alert.fingerprint"],
        ),
        Index("ix_lati_tenant_fingerprint_deleted", "tenant_id", "fingerprint", "deleted_at"),
        Index("ix_lati_tenant_deleted_fingerprint", "tenant_id", "deleted_at", "fingerprint"),
    )


# -----------------------------
# Escalation policy (per-tenant)
# -----------------------------

class AlertEscalationPolicy(SQLModel, table=True):
    """
    Defines how alerts escalate for a tenant.
    steps: JSON list of escalation steps.
      Example:
      [
        {"after_seconds": 0,   "channel": "internal", "target": "oncall-inbox"},
        {"after_seconds": 120, "channel": "slack",    "target": "#oncall", "rate_limit_per_min": 60},
        {"after_seconds": 600, "channel": "pager",    "target": "primary-oncall"},
      ]
    """
    __tablename__ = "alert_escalation_policy"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: str = Field(foreign_key="tenant.id", nullable=False, index=True, max_length=64)

    name: str = Field(nullable=False, index=True, max_length=128)
    enabled: bool = Field(default=True, nullable=False)

    # Optional scoping
    provider_type: Optional[str] = Field(default=None, index=True, max_length=64)
    fingerprint_prefix: Optional[str] = Field(default=None, index=True, max_length=128)

    # SLA target (overall)
    sla_seconds: int = Field(default=900, nullable=False)  # 15 min default

    # Escalation steps
    steps: List[Dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(SAJSON, nullable=False),
    )

    created_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False, index=True, sa_column_kwargs={"onupdate": utcnow})

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_escalation_policy_tenant_name"),
        Index("ix_policy_tenant_enabled", "tenant_id", "enabled"),
    )


# -----------------------------
# Escalation state machine (per alert)
# -----------------------------

class AlertEscalationState(SQLModel, table=True):
    """
    Tracks escalation progress for a specific alert.
    Throughput controls:
      - next_run_at: scheduler field
      - locked_by / locked_until: leasing to avoid multi-worker duplicate sends
      - attempts: retry count
    """
    __tablename__ = "alert_escalation_state"

    alert_id: UUID = Field(
        sa_column=Column(ForeignKey("alert.id", ondelete="CASCADE"), primary_key=True),
    )
    tenant_id: str = Field(foreign_key="tenant.id", nullable=False, index=True, max_length=64)

    policy_id: Optional[UUID] = Field(default=None, foreign_key="alert_escalation_policy.id", index=True)

    status: EscalationStatus = Field(
        default=EscalationStatus.OPEN,
        sa_column=Column(SAEnum(EscalationStatus, name="escalation_status"), nullable=False),
        index=True,
    )

    # What step we’re on (0-based)
    step_index: int = Field(default=0, nullable=False)

    # When to run next escalation attempt
    next_run_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)

    # SLA deadline for ack/resolve
    sla_deadline_at: datetime = Field(default_factory=lambda: utcnow() + timedelta(seconds=900), nullable=False, index=True)

    # Lease/lock fields for multi-worker throughput
    locked_by: Optional[str] = Field(default=None, index=True, max_length=128)
    locked_until: Optional[datetime] = Field(default=None, index=True)

    attempts: int = Field(default=0, nullable=False)
    last_error: Optional[str] = Field(default=None, sa_column=Column(SAText, nullable=True))

    created_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False, index=True, sa_column_kwargs={"onupdate": utcnow})

    alert: Alert = Relationship(back_populates="escalation_state")

    __table_args__ = (
        Index("ix_escal_state_due", "tenant_id", "status", "next_run_at"),
        Index("ix_escal_state_lock", "locked_until", "locked_by"),
        Index("ix_escal_state_sla", "tenant_id", "status", "sla_deadline_at"),
    )


# -----------------------------
# Outbox for notification delivery (throughput + retry)
# -----------------------------

class AlertEscalationOutbox(SQLModel, table=True):
    """
    Delivery queue for escalation notifications.
    This is what your workers consume. It is designed for high throughput:
      - status + next_attempt_at
      - attempts + last_error
      - dedupe_key to prevent spam storms
    """
    __tablename__ = "alert_escalation_outbox"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    tenant_id: str = Field(foreign_key="tenant.id", nullable=False, index=True, max_length=64)
    alert_id: UUID = Field(foreign_key="alert.id", nullable=False, index=True)

    channel: EscalationChannel = Field(
        sa_column=Column(SAEnum(EscalationChannel, name="escalation_channel"), nullable=False),
        index=True,
    )
    target: str = Field(nullable=False, index=True, max_length=256)

    payload: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(SAJSON, nullable=False),
    )

    status: OutboxStatus = Field(
        default=OutboxStatus.PENDING,
        sa_column=Column(SAEnum(OutboxStatus, name="outbox_status"), nullable=False),
        index=True,
    )

    # Dedupe prevents “same alert step” from spamming repeatedly
    dedupe_key: str = Field(nullable=False, max_length=256)

    next_attempt_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)
    attempts: int = Field(default=0, nullable=False)
    last_error: Optional[str] = Field(default=None, sa_column=Column(SAText, nullable=True))

    created_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False, index=True, sa_column_kwargs={"onupdate": utcnow})

    __table_args__ = (
        UniqueConstraint("tenant_id", "dedupe_key", name="uq_outbox_tenant_dedupe"),
        Index("ix_outbox_due", "status", "next_attempt_at"),
        Index("ix_outbox_tenant_due", "tenant_id", "status", "next_attempt_at"),
    )