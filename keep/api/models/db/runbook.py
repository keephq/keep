from uuid import UUID, uuid4
from datetime import datetime
from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import Column, ForeignKey, Text
from pydantic import BaseModel


# RunbookContent Model
class RunbookContent(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    runbook_id: UUID = Field(
        sa_column=Column(ForeignKey("runbook.id", ondelete="CASCADE"))  # Foreign key with CASCADE delete
    )
    runbook: Optional["Runbook"] = Relationship(back_populates="contents")
    content: str = Field(sa_column=Column(Text), nullable=False)  # Using SQLAlchemy's Text type
    link: str = Field(sa_column=Column(Text), nullable=False)  # Using SQLAlchemy's Text type
    encoding: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)  # Timestamp for creation

    class Config:
        orm_mode = True

# Runbook Model
class Runbook(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(
        sa_column=Column(ForeignKey("tenant.id", ondelete="CASCADE"))  # Foreign key with CASCADE delete
    )
    repo_id: str  # Repository ID
    relative_path: str = Field(sa_column=Column(Text), nullable=False)  # Path in the repo, must be set
    title: str = Field(sa_column=Column(Text), nullable=False)  # Title of the runbook, must be set
    contents: List["RunbookContent"] = Relationship(back_populates="runbook")  # Relationship to RunbookContent
    provider_type: str  # Type of the provider
    provider_id: Optional[str] = None  # Optional provider ID
    created_at: datetime = Field(default_factory=datetime.utcnow)  # Timestamp for creation

    class Config:
        orm_mode = True  # Enable ORM mode for compatibility with Pydantic models

        
class RunbookDto(BaseModel, extra="ignore"):
    id: UUID
    tenant_id: str
    repo_id: str
    relative_path: str
    title: str
    contents: List["RunbookContent"] = []
    provider_type: str
    provider_id: Optional[str] = None

class RunbookContentDto(BaseModel, extra="ignore"):
    id: UUID
    content: str
    link: str
    encoding: Optional[str] = None

    @classmethod
    def from_orm(cls, content: "RunbookContent") -> "RunbookContentDto":
        return cls(
            id=content.id,
            content=content.content,
            link=content.link,
            encoding=content.encoding
        )

class RunbookDtoOut(RunbookDto):
   contents: List[RunbookContentDto] = []
   @classmethod
   def from_orm(
       cls, runbook: "Runbook"
   ) -> "RunbookDtoOut":
       return cls(
           id=runbook.id,
           title=runbook.title,
           tenant_id=runbook.tenant_id,
           repo_id=runbook.repo_id,
           relative_path=runbook.relative_path,
           provider_type=runbook.provider_type,
           provider_id=runbook.provider_id,
           contents=[RunbookContentDto.from_orm(content) for content in runbook.contents]
       )
