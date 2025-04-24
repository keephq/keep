import enum
from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy_utils import UUIDType
from sqlmodel import JSON, TEXT, Column, Field, ForeignKey, Index, SQLModel

from keep.api.models.db.alert import DATETIME_COLUMN_TYPE


class EnrichmentType(str, enum.Enum):
    MAPPING = "mapping"
    EXTRACTION = "extraction"


class EnrichmentStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


class EnrichmentEvent(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id", index=True)
    timestamp: datetime = Field(
        sa_column=Column(DATETIME_COLUMN_TYPE, nullable=False),
        default_factory=lambda: datetime.now(tz=timezone.utc),
    )
    enriched_fields: dict = Field(sa_column=Column(JSON), default_factory=dict)
    status: str
    enrichment_type: str = Field()  # 'mapping' or 'extraction'
    rule_id: int | None = Field(default=None)  # ID of the mapping/extraction rule
    alert_id: UUID = Field(
        sa_column=Column(
            UUIDType(binary=False),
            nullable=False,
        )
    )
    enriched_fields: dict = Field(sa_column=Column(JSON), default_factory=dict)
    date_hour: datetime = Field(
        sa_column=Column(DATETIME_COLUMN_TYPE),
        default_factory=lambda: datetime.now(tz=timezone.utc).replace(
            minute=0, second=0, microsecond=0
        ),
    )

    __table_args__ = (
        Index(
            "ix_enrichment_event_status",
            "status",
        ),
        Index(
            "ix_enrichment_event_tenant_id_date_hour",
            "tenant_id",
            "date_hour",
        ),
        Index(
            "ix_enrichment_event_alert_id",
            "alert_id",
        ),
        Index(
            "ix_enrichment_event_rule_id",
            "rule_id",
        ),
    )

    class Config:
        arbitrary_types_allowed = True


class EnrichmentLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id", index=True)
    enrichment_event_id: UUID = Field(
        sa_column=Column(
            UUIDType(binary=False),
            ForeignKey("enrichmentevent.id", ondelete="CASCADE"),
            nullable=False,
        ),
        default_factory=lambda: uuid4(),
    )
    timestamp: datetime = Field(
        sa_column=Column(DATETIME_COLUMN_TYPE, nullable=False),
        default_factory=lambda: datetime.now(tz=timezone.utc),
    )
    message: str = Field(sa_column=Column(TEXT))

    __table_args__ = (
        Index(
            "ix_enrichment_log_tenant_id_timestamp",
            "tenant_id",
            "timestamp",
        ),
        Index(
            "ix_enrichment_log_enrichment_event_id",
            "enrichment_event_id",
        ),
    )


class EnrichmentEventWithLogs(BaseModel):
    enrichment_event: EnrichmentEvent
    logs: list[EnrichmentLog]
