from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, Index
from sqlalchemy import Enum as SAEnum
from sqlalchemy import JSON as SAJSON
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class AISuggestionType(str, enum.Enum):
    INCIDENT_SUGGESTION = "incident_suggestion"
    SUMMARY_GENERATION = "summary_generation"
    OTHER = "other"


class AISuggestion(SQLModel, table=True):
    """
    Stores an AI-generated suggestion plus the input that produced it.
    Feedback is stored in AIFeedback.
    """

    __tablename__ = "ai_suggestion"
    __table_args__ = (
        # Common lookup patterns: find suggestions per tenant/user/type, and de-dupe by hash.
        Index("ix_ai_suggestion_tenant_user_created", "tenant_id", "user_id", "created_at"),
        Index("ix_ai_suggestion_tenant_type_created", "tenant_id", "suggestion_type", "created_at"),
        Index("ix_ai_suggestion_tenant_hash_type", "tenant_id", "suggestion_input_hash", "suggestion_type"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    tenant_id: str = Field(foreign_key="tenant.id", nullable=False, index=True, max_length=64)
    user_id: str = Field(nullable=False, index=True, max_length=64)

    # the input that the user provided to the AI
    suggestion_input: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(SAJSON, nullable=False),
    )

    # hash of the suggestion input (used for dedupe / caching)
    suggestion_input_hash: str = Field(nullable=False, index=True, max_length=128)

    # the type of suggestion
    suggestion_type: AISuggestionType = Field(
        nullable=False,
        sa_column=Column(SAEnum(AISuggestionType, name="ai_suggestion_type"), nullable=False),
        index=True,
    )

    # the content of the suggestion
    suggestion_content: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(SAJSON, nullable=False),
    )

    # the model that was used to generate the suggestion (e.g., "gpt-4.1", "claude-3", etc.)
    model: str = Field(nullable=False, index=True, max_length=128)

    created_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)

    feedbacks: List["AIFeedback"] = Relationship(
        back_populates="suggestion",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class AIFeedback(SQLModel, table=True):
    """
    Stores user feedback about a suggestion (rating + comment + structured JSON if needed).
    """

    __tablename__ = "ai_feedback"
    __table_args__ = (
        Index("ix_ai_feedback_suggestion_created", "suggestion_id", "created_at"),
        Index("ix_ai_feedback_user_created", "user_id", "created_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    suggestion_id: UUID = Field(
        foreign_key="ai_suggestion.id",
        nullable=False,
        index=True,
    )

    user_id: str = Field(nullable=False, index=True, max_length=64)

    # If you want structured feedback (thumbs up/down + reasons, tags, etc.)
    feedback_content: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(SAJSON, nullable=False),
    )

    # Optional scalar rating (you can constrain range at app layer or add CheckConstraint if you want)
    rating: Optional[int] = Field(default=None)

    comment: Optional[str] = Field(default=None, max_length=2000)

    created_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)
    updated_at: datetime = Field(
        default_factory=utcnow,
        nullable=False,
        sa_column_kwargs={"onupdate": utcnow},
        index=True,
    )

    suggestion: AISuggestion = Relationship(back_populates="feedbacks")