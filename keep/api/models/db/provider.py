from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, ForeignKey, SQLModel


class Provider(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    name: str
    description: Optional[str]
    type: str
    installed_by: str
    installation_time: datetime
    configuration_key: str

    class Config:
        orm_mode = True
        unique_together = ["tenant_id", "name"]
