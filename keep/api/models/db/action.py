from datetime import datetime
from typing import ClassVar

from sqlalchemy import UniqueConstraint
from sqlmodel import TEXT, Column, Field, SQLModel


class Action(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("tenant_id", "name", "use"),)

    id: str = Field(default=None, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    use: str
    name: str
    description: str | None
    action_raw: str = Field(sa_column=Column(TEXT))
    installed_by: str
    installation_time: datetime

    class Config:
        orm_mode = True
        unique_together: ClassVar[list[str]] = ["tenant_id", "name", "use"]
