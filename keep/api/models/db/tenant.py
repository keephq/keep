from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class Tenant(SQLModel, table=True):
    # uuid
    id: str = Field(primary_key=True)
    name: str


class TenantProduct(SQLModel, table=True):
    id: int = Field(primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id")
    name: str


class TenantApiKey(SQLModel, table=True):
    tenant_id: str = Field(foreign_key="tenant.id")
    product_id: Optional[int] = Field(default=None, foreign_key="tenantproduct.id")
    key_hash: str = Field(primary_key=True)
    tenant: Tenant = Relationship()
