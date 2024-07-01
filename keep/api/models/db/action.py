from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import TEXT, Column, Field, SQLModel


class Action(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("tenant_id", "name", "use"),)

    id: str = Field(
        default_factory=lambda: str(uuid4()), primary_key=True, max_length=36
    )
    tenant_id: str = Field(foreign_key="tenant.id", max_length=36)
    use: str
    name: str
    description: Optional[str]
    action_raw: str = Field(sa_column=Column(TEXT))
    installed_by: str
    installation_time: datetime

    class Config:
        orm_mode = True
        unique_together = ["tenant_id", "name", "use"]
