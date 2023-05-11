from sqlmodel import Field, Relationship, SQLModel


class Tenant(SQLModel, table=True):
    # uuid
    id: str = Field(primary_key=True)
    name: str


class TenantApiKey(SQLModel, table=True):
    tenant_id: str = Field(foreign_key="tenant.id")
    reference_id: str = Field(
        unique=True, description="For instance, the GitHub installation ID"
    )
    key_hash: str = Field(primary_key=True)
    tenant: Tenant = Relationship()
