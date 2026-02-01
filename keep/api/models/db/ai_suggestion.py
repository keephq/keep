import enum
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel


class AISuggestionType(enum.Enum):
    INCIDENT_SUGGESTION = "incident_suggestion"
    SUMMARY_GENERATION = "summary_generation"
    OTHER = "other"


class AISuggestion(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id", index=True)
    user_id: str = Field(index=True)
    # the input that the user provided to the AI
    suggestion_input: Dict = Field(sa_column=Column(JSON))
    # the hash of the suggestion input to allow for duplicate suggestions with the same input
    suggestion_input_hash: str = Field(index=True)
    # the type of suggestion
    suggestion_type: AISuggestionType = Field(index=True)
    # the content of the suggestion
    suggestion_content: Dict = Field(sa_column=Column(JSON))
    # the model that was used to generate the suggestion
    model: str = Field()
    # the date and time when the suggestion was created
    created_at: datetime = Field(default_factory=datetime.utcnow)

    feedbacks: List["AIFeedback"] = Relationship(back_populates="suggestion")

    class Config:
        arbitrary_types_allowed = True


class AIFeedback(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    suggestion_id: UUID = Field(foreign_key="aisuggestion.id", index=True)
    user_id: str = Field(index=True)
    feedback_content: str = Field(sa_column=Column(JSON))
    rating: Optional[int] = Field(default=None)
    comment: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    suggestion: AISuggestion = Relationship(back_populates="feedbacks")

    class Config:
        arbitrary_types_allowed = True
