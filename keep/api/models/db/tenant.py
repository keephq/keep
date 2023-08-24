from typing import List, Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel


class Tenant(SQLModel, table=True):
    # uuid
    id: str = Field(primary_key=True)
    name: str
    installations: List["TenantInstallation"] = Relationship(back_populates="tenant")


class TenantApiKey(SQLModel, table=True):
    tenant_id: str = Field(foreign_key="tenant.id")
    reference_id: str = Field(description="For instance, the GitHub installation ID")
    key_hash: str = Field(primary_key=True)
    tenant: Tenant = Relationship()
    is_system: bool = False
    system_description: Optional[str] = None

    class Config:
        orm_mode = True
        unique_together = ["tenant_id", "reference_id"]


class TenantInstallation(SQLModel, table=True):
    id: UUID = Field(default=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    bot_id: str
    installed: bool = False
    tenant: Optional[Tenant] = Relationship(back_populates="installations")
