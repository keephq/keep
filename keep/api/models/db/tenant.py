from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class Tenant(SQLModel, table=True):
    # uuid
    id: str = Field(max_length=36, primary_key=True)
    name: str


class TenantApiKey(SQLModel, table=True):
    tenant_id: str = Field(foreign_key="tenant.id", max_length=36)
    reference_id: str = Field(description="For instance, the GitHub installation ID")
    key_hash: str = Field(primary_key=True, max_length=64)
    tenant: Tenant = Relationship()
    is_system: bool = False
    is_deleted: bool = False
    system_description: Optional[str] = None
    created_by: str
    role: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: str = Field(default=None)

    class Config:
        orm_mode = True
        unique_together = ["tenant_id", "reference_id"]
