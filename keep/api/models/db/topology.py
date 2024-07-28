from typing import List, Optional

from sqlmodel import JSON, Column, Field, Relationship, SQLModel


class TopologyService(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    source_provider_id: Optional[str]
    repository: Optional[str]
    tags: Optional[List[str]] = Field(sa_column=Column(JSON))
    service: str
    display_name: str
    description: Optional[str]
    team: Optional[str]
    application: Optional[str]
    email: Optional[str]
    slack: Optional[str]

    dependencies: List["TopologyServiceDependency"] = Relationship(
        back_populates="service"
    )


class TopologyServiceDependency(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    service_id: str = Field(foreign_key="service.id")
    dependent_service_id: str = Field(foreign_key="service.id")
    protocol: Optional[str]

    service: TopologyService = Relationship(back_populates="dependencies")
