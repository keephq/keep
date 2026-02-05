import datetime

from sqlalchemy import Column, LargeBinary
from sqlmodel import Field, SQLModel


class ProviderImage(SQLModel, table=True):
    id: str = Field(primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    image_name: str
    image_blob: bytes = Field(sa_column=Column(LargeBinary))
    last_updated: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.timezone.utc)
    )
    updated_by: str = Field(default="system", max_length=255)
