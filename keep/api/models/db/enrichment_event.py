from __future__ import annotations

import enum
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, field_validator
from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy import Enum as SAEnum
from sqlalchemy import JSON as SAJSON
from sqlalchemy import Text as SAText
from sqlalchemy_utils import UUIDType
from sqlmodel import Field, SQLModel

from keep.api.models.db.alert import DATETIME_COLUMN_TYPE


# --------------- helpers ---------------

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """
    Normalize datetime to timezone-aware UTC.
    - If naive: assume UTC (because otherwise you're already lying to yourself).
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def hour_bucket(dt: Optional[datetime] = None) -> datetime:
    """
    Hour bucket in UTC, always timezone-aware.
    """
    t = ensure_utc(dt or utcnow())
    return t.replace(minute=0, second=0, microsecond=0)


# --------------- enums ---------------

class EnrichmentType(str, enum.Enum):
    MAPPING = "mapping"
    EXTRACTION = "extraction"


class EnrichmentStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    # If you want future flexibility, add:
    # PENDING = "pending"


# --------------- models ---------------

class EnrichmentEvent(SQLModel, table=True):
    """
    One enrichment run applied to an alert, with outcome.

    Notes:
    - Enum columns use native_enum=False to avoid PostgreSQL enum-type migration headaches.
    - enriched_fields is validated for JSON-serializability and size.
    """

    __tablename__ = "enrichment_event"

    # App-level guardrail: keep this sane. Adjust if needed.
    MAX_ENRICHED_FIELDS_BYTES: int = 1_000_000  # 1MB

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    tenant_id: str = Field(
        foreign_key="tenant.id",
        nullable=False,
        index=False,  # covered by composite indexes below
        max_length=64,
    )

    timestamp: datetime = Field(
        sa_column=Column(DATETIME_COLUMN_TYPE, nullable=False),
        default_factory=utcnow,
    )

    date_hour: datetime = Field(
        sa_column=Column(DATETIME_COLUMN_TYPE, nullable=False),
        default_factory=hour_bucket,
    )

    status: EnrichmentStatus = Field(
        sa_column=Column(
            SAEnum(
                EnrichmentStatus,
                native_enum=False,  # store as VARCHAR, no PG enum type object
                length=50,
            ),
            nullable=False,
        ),
        index=False,  # composite indexes cover typical queries
    )

    enrichment_type: EnrichmentType = Field(
        sa_column=Column(
            SAEnum(
                EnrichmentType,
                native_enum=False,  # store as VARCHAR
                length=50,
            ),
            nullable=False,
        ),
        index=False,
    )

    rule_id: Optional[int] = Field(default=None, index=True)

    # NOTE on delete behavior:
    # - CASCADE removes enrichment history when alert is deleted.
    # - If you want audit retention, consider RESTRICT or SET NULL + nullable=True.
    alert_id: UUID = Field(
        sa_column=Column(
            UUIDType(binary=False),
            ForeignKey("alert.id", ondelete="CASCADE"),
            nullable=False,
        ),
        index=False,  # covered by composite index below
    )

    enriched_fields: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(SAJSON, nullable=False),
    )

    # ---- validators ----

    @field_validator("timestamp", "date_hour")
    @classmethod
    def _validate_datetimes_are_utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("enriched_fields")
    @classmethod
    def _validate_enriched_fields_json(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enforce:
        - JSON serializable
        - size cap (bytes)
        """
        try:
            serialized = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as e:
            raise ValueError(f"enriched_fields not JSON-serializable: {e}") from e

        size = len(serialized.encode("utf-8"))
        if size > cls.MAX_ENRICHED_FIELDS_BYTES:
            raise ValueError(
                f"enriched_fields too large ({size} bytes). "
                f"Max allowed is {cls.MAX_ENRICHED_FIELDS_BYTES} bytes."
            )

        return v

    # ---- repr ----

    def __repr__(self) -> str:
        return (
            f"EnrichmentEvent(id={self.id}, tenant_id={self.tenant_id}, "
            f"type={self.enrichment_type}, status={self.status}, alert_id={self.alert_id})"
        )

    __table_args__ = (
        # Real-world: tenant + timestamp range queries
        Index("ix_enrichment_event_tenant_id_timestamp", "tenant_id", "timestamp"),

        # Aggregations / dashboards
        Index("ix_enrichment_event_tenant_id_date_hour", "tenant_id", "date_hour"),
        Index(
            "ix_enrichment_event_tenant_id_status_date_hour",
            "tenant_id",
            "status",
            "date_hour",
        ),
        Index(
            "ix_enrichment_event_tenant_id_type_date_hour",
            "tenant_id",
            "enrichment_type",
            "date_hour",
        ),
        Index("ix_enrichment_event_tenant_id_alert_id", "tenant_id", "alert_id"),
    )


class EnrichmentLog(SQLModel, table=True):
    """
    Log lines associated with an enrichment event.
    """

    __tablename__ = "enrichment_log"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    tenant_id: str = Field(
        foreign_key="tenant.id",
        nullable=False,
        index=False,  # covered by composite index
        max_length=64,
    )

    enrichment_event_id: UUID = Field(
        sa_column=Column(
            UUIDType(binary=False),
            ForeignKey("enrichment_event.id", ondelete="CASCADE"),
            nullable=False,
        ),
        index=False,  # covered by composite index
    )

    timestamp: datetime = Field(
        sa_column=Column(DATETIME_COLUMN_TYPE, nullable=False),
        default_factory=utcnow,
    )

    message: str = Field(sa_column=Column(SAText, nullable=False))

    @field_validator("timestamp")
    @classmethod
    def _validate_log_timestamp_is_utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    def __repr__(self) -> str:
        return (
            f"EnrichmentLog(id={self.id}, tenant_id={self.tenant_id}, "
            f"event_id={self.enrichment_event_id}, timestamp={self.timestamp.isoformat()})"
        )

    __table_args__ = (
        Index("ix_enrichment_log_tenant_id_timestamp", "tenant_id", "timestamp"),
        Index("ix_enrichment_log_event_id_timestamp", "enrichment_event_id", "timestamp"),
    )


class EnrichmentEventWithLogs(BaseModel):
    enrichment_event: EnrichmentEvent
    logs: list[EnrichmentLog]