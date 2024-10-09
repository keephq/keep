import logging
from uuid import UUID, uuid4
from datetime import datetime
from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel, DateTime
from sqlalchemy import Column, ForeignKey, Text
from pydantic import BaseModel
from sqlalchemy_utils import UUIDType
from keep.api.core.config import config
from sqlalchemy.dialects.mysql import DATETIME as MySQL_DATETIME
from sqlalchemy.dialects.mssql import DATETIME2 as MSSQL_DATETIME2
from keep.api.consts import RUNNING_IN_CLOUD_RUN
from sqlalchemy.engine.url import make_url


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

class RunbookToIncident(SQLModel, table=True):
    tenant_id: str = Field(foreign_key="tenant.id")
    runbook_id: UUID = Field(foreign_key="runbook.id", primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    incident_id: UUID = Field(
        sa_column=Column(
            UUIDType(binary=False),
            ForeignKey("incident.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )

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
    file_name: str
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
    timestamp: datetime = Field(
        sa_column=Column(datetime_column_type, index=True),
        default_factory=lambda: datetime.utcnow().replace(
            microsecond=int(datetime.utcnow().microsecond / 1000) * 1000
        ),
    )
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
    file_name: str
    encoding: Optional[str] = None

    @classmethod
    def from_orm(cls, content: "RunbookContent") -> "RunbookContentDto":
        return cls(
            id=content.id,
            content=content.content,
            link=content.link,
            encoding=content.encoding,
            file_name=content.file_name
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
