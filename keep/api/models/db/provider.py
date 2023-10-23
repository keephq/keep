from datetime import datetime
from typing import Optional

from sqlmodel import JSON, Column, Field, SQLModel


class Provider(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    name: str
    description: Optional[str]
    type: str
    installed_by: str
    installation_time: datetime
    configuration_key: str
    validatedScopes: dict = Field(
        sa_column=Column(JSON)
    )  # scope name is key and value is either True if validated or string with error message, e.g: {"read": True, "write": "error message"}
    consumer: bool = False

    class Config:
        orm_mode = True
        unique_together = ["tenant_id", "name"]
