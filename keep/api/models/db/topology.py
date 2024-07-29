from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey
from sqlmodel import JSON, Column, Field, Relationship, SQLModel, func


class TopologyService(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, default=None)
    tenant_id: str = Field(sa_column=Column(ForeignKey("tenant.id")))
    source_provider_id: str = "unknown"
    repository: Optional[str]
    tags: Optional[List[str]] = Field(sa_column=Column(JSON))
    service: str
    environment: str = Field(default="unknown")
    display_name: str
    description: Optional[str]
    team: Optional[str]
    application: Optional[str]
    email: Optional[str]
    slack: Optional[str]
    updated_at: Optional[datetime] = Field(
        sa_column=Column(
            DateTime(timezone=True),
            name="updated_at",
            onupdate=func.now(),
            server_default=func.now(),
        )
    )

    dependencies: List["TopologyServiceDependency"] = Relationship(
        back_populates="service",
        sa_relationship_kwargs={
            "foreign_keys": "[TopologyServiceDependency.service_id]"
        },
    )

    class Config:
        orm_mode = True
        unique_together = ["tenant_id", "service", "environment", "source_provider_id"]


class TopologyServiceDependency(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, default=None)
    service_id: int = Field(
        sa_column=Column(ForeignKey("topologyservice.id", ondelete="CASCADE"))
    )
    depends_on_service_id: int = Field(
        sa_column=Column(ForeignKey("topologyservice.id", ondelete="CASCADE"))
    )  # service_id calls deponds_on_service_id (A->B)
    protocol: Optional[str] = "unknown"
    updated_at: Optional[datetime] = Field(
        sa_column=Column(
            DateTime(timezone=True),
            name="updated_at",
            onupdate=func.now(),
            server_default=func.now(),
        )
    )

    service: TopologyService = Relationship(
        back_populates="dependencies",
        sa_relationship_kwargs={
            "foreign_keys": "[TopologyServiceDependency.service_id]"
        },
    )
    dependent_service: TopologyService = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[TopologyServiceDependency.depends_on_service_id]"
        }
    )


class TopologyServiceDtoBase(BaseModel, extra="ignore"):
    source_provider_id: Optional[str]
    repository: Optional[str] = None
    tags: Optional[List[str]] = None
    service: str
    display_name: str
    environment: str = "unknown"
    description: Optional[str] = None
    team: Optional[str] = None
    application: Optional[str] = None
    email: Optional[str] = None
    slack: Optional[str] = None


class TopologyServiceInDto(TopologyServiceDtoBase):
    dependencies: dict[str, str] = {}  # dict of service it depends on : protocol


class TopologyServiceDependencyDto(BaseModel, extra="ignore"):
    serviceId: int
    protocol: Optional[str] = "unknown"


class TopologyServiceDtoOut(TopologyServiceDtoBase):
    id: int
    dependencies: List[TopologyServiceDependencyDto]
    updated_at: Optional[datetime]

    @classmethod
    def from_orm(cls, service: "TopologyService") -> "TopologyServiceDtoOut":
        return cls(
            id=service.id,
            source_provider_id=service.source_provider_id,
            repository=service.repository,
            tags=service.tags,
            service=service.service,
            display_name=service.display_name,
            environment=service.environment,
            description=service.description,
            team=service.team,
            application=service.application,
            email=service.email,
            slack=service.slack,
            dependencies=[
                TopologyServiceDependencyDto(
                    serviceId=dep.depends_on_service_id, protocol=dep.protocol
                )
                for dep in service.dependencies
            ],
            updated_at=service.updated_at,
        )
