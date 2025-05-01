from datetime import datetime
from typing import List
from uuid import UUID, uuid4

from sqlalchemy import Column, ForeignKey, Text
from sqlalchemy_utils import UUIDType
from sqlmodel import Field, JSON, SQLModel

from keep.api.models.db.incident import Incident, IncidentStatus


class IncidentComment(SQLModel, table=True):
    """Model for storing incident comments with mentioned users."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    incident_id: UUID = Field(
        sa_column=Column(
            UUIDType(binary=False),
            ForeignKey("incident.id", ondelete="CASCADE"),
            index=True,
        )
    )
    status: str = Field(sa_column=Column(Text, nullable=False))
    comment: str = Field(sa_column=Column(Text, nullable=False))
    mentioned_users: List[str] = Field(default=[], sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
    )
    created_by: str | None = Field(default=None)