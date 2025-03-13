import enum
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import PrivateAttr
from retry import retry
from sqlalchemy import ForeignKey, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy_utils import UUIDType
from sqlmodel import (
    JSON,
    TEXT,
    Column,
    Field,
    Index,
    Relationship,
    Session,
    SQLModel,
    func,
    select,
    text,
)

from keep.api.models.alert import SeverityBaseInterface
from keep.api.models.db.rule import ResolveOn
from keep.api.models.db.tenant import Tenant


class IncidentType(str, enum.Enum):
    MANUAL = "manual"  # Created manually by users
    AI = "ai"  # Created by AI
    RULE = "rule"  # Created by rules engine
    TOPOLOGY = "topology"  # Created by topology processor


class IncidentSeverity(SeverityBaseInterface):
    CRITICAL = ("critical", 5)
    HIGH = ("high", 4)
    WARNING = ("warning", 3)
    INFO = ("info", 2)
    LOW = ("low", 1)

    def from_number(n):
        for severity in IncidentSeverity:
            if severity.order == n:
                return severity
        raise ValueError(f"No IncidentSeverity with order {n}")


class IncidentStatus(enum.Enum):
    # Active incident
    FIRING = "firing"
    # Incident has been resolved
    RESOLVED = "resolved"
    # Incident has been acknowledged but not resolved
    ACKNOWLEDGED = "acknowledged"
    # Incident was merged with another incident
    MERGED = "merged"
    # Incident was removed
    DELETED = "deleted"


class Incident(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    tenant: Tenant = Relationship()

    # Auto-incrementing number per tenant
    running_number: Optional[int] = Field(default=None)

    user_generated_name: str | None
    ai_generated_name: str | None

    user_summary: str = Field(sa_column=Column(TEXT))
    generated_summary: str = Field(sa_column=Column(TEXT))

    assignee: str | None
    severity: int = Field(default=IncidentSeverity.CRITICAL.order)
    forced_severity: bool = Field(default=False)

    status: str = Field(default=IncidentStatus.FIRING.value, index=True)

    creation_time: datetime = Field(default_factory=datetime.utcnow)

    # Start/end should be calculated from first/last alerts
    # But I suppose to have this fields as cache, to prevent extra requests
    start_time: datetime | None
    end_time: datetime | None
    last_seen_time: datetime | None

    is_predicted: bool = Field(default=False)
    is_confirmed: bool = Field(default=False)

    alerts_count: int = Field(default=0)
    affected_services: list = Field(sa_column=Column(JSON), default_factory=list)
    sources: list = Field(sa_column=Column(JSON), default_factory=list)

    rule_id: UUID | None = Field(
        sa_column=Column(
            UUIDType(binary=False),
            ForeignKey("rule.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # Note: IT IS NOT A UNIQUE IDENTIFIER (as in alerts)
    rule_fingerprint: str = Field(default="", sa_column=Column(TEXT))
    # This is the fingerprint of the incident generated by the underlying tool
    # It's not a unique identifier in the DB (constraint), but when we have the same incident from some tools, we can use it to detect duplicates
    fingerprint: str | None = Field(default=None, sa_column=Column(TEXT))

    incident_type: str = Field(default=IncidentType.MANUAL.value)
    # for topology incidents
    incident_application: UUID | None = Field(default=None)
    resolve_on: str = ResolveOn.ALL.value

    same_incident_in_the_past_id: UUID | None = Field(
        sa_column=Column(
            UUIDType(binary=False),
            ForeignKey("incident.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    same_incident_in_the_past: Optional["Incident"] = Relationship(
        back_populates="same_incidents_in_the_future",
        sa_relationship_kwargs=dict(
            remote_side="Incident.id",
            foreign_keys="[Incident.same_incident_in_the_past_id]",
        ),
    )

    same_incidents_in_the_future: List["Incident"] = Relationship(
        back_populates="same_incident_in_the_past",
        sa_relationship_kwargs=dict(
            foreign_keys="[Incident.same_incident_in_the_past_id]",
        ),
    )

    merged_into_incident_id: UUID | None = Field(
        sa_column=Column(
            UUIDType(binary=False),
            ForeignKey("incident.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    merged_at: datetime | None = Field(default=None)
    merged_by: str | None = Field(default=None)
    merged_into: Optional["Incident"] = Relationship(
        back_populates="merged_incidents",
        sa_relationship_kwargs=dict(
            remote_side="Incident.id",
            foreign_keys="[Incident.merged_into_incident_id]",
        ),
    )
    merged_incidents: List["Incident"] = Relationship(
        back_populates="merged_into",
        sa_relationship_kwargs=dict(
            foreign_keys="[Incident.merged_into_incident_id]",
        ),
    )

    # @tb: _alerts is Alert, not explicitly typed because of circular dependency
    _alerts: List = PrivateAttr(default_factory=list)
    _enrichments: dict = PrivateAttr(default={})

    class Config:
        arbitrary_types_allowed = True

    __table_args__ = (
        Index(
            "ix_incident_tenant_running_number",
            "tenant_id",
            "running_number",
            unique=True,
            postgresql_where=text("running_number IS NOT NULL"),  # For PostgreSQL
            sqlite_where=text("running_number IS NOT NULL"),  # For SQLite
        ),
    )

    @property
    def alerts(self):
        return self._alerts

    @property
    def enrichments(self):
        return getattr(self, "_enrichments", {})


@retry(exceptions=(IntegrityError,), tries=3, delay=0.1, backoff=2, jitter=(0, 0.1))
def get_next_running_number(session, tenant_id: str) -> int:
    """Get the next running number for a tenant."""
    try:
        # Get the maximum running number for the tenant
        result = session.exec(
            select(func.max(Incident.running_number)).where(
                Incident.tenant_id == tenant_id
            )
        ).first()

        # If no incidents exist yet, start from 1
        next_number = (result or 0) + 1
        return next_number
    except IntegrityError:
        session.rollback()
        # Refresh the session's view of the data
        session.expire_all()
        raise


@event.listens_for(Incident, "before_insert")
def set_running_number(mapper, connection, target):
    if target.running_number is None:
        # Create a temporary session to get the next running number
        with Session(connection) as session:
            try:
                target.running_number = get_next_running_number(
                    session, target.tenant_id
                )
            except Exception:
                target.running_number = None


# def upgrade() -> None:
#     # ### commands auto generated by Alembic - please adjust! ###
#     with op.batch_alter_table("incident", schema=None) as batch_op:
#         batch_op.add_column(sa.Column("running_number", sa.Integer(), nullable=True))
#     op.create_index(
#         "ix_incident_tenant_running_number",
#         "incident",
#         ["tenant_id", "running_number"],
#         unique=True,
#         postgresql_where=text("running_number IS NOT NULL"),
#         mysql_where=text("running_number IS NOT NULL"),
#         sqlite_where=text("running_number IS NOT NULL"),
#     )
