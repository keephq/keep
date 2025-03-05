from sqlalchemy import Column, LargeBinary
from sqlmodel import Field, SQLModel


class ProviderImage(SQLModel, table=True):
    id: str = Field(primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    image_name: str
    image_blob: bytes = Field(sa_column=Column(LargeBinary))
