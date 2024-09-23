from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey
from sqlmodel import JSON, Column, Field, Relationship, SQLModel, func


class TopologyServiceApplication(SQLModel, table=True):
    service_id: int = Field(foreign_key="topologyservice.id", primary_key=True)
    application_id: UUID = Field(foreign_key="topologyapplication.id", primary_key=True)


class TopologyApplication(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(sa_column=Column(ForeignKey("tenant.id")))
    name: str
    description: Optional[str] = None
    services: List["TopologyService"] = Relationship(
        back_populates="applications", link_model=TopologyServiceApplication
    )


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
    email: Optional[str]
    slack: Optional[str]
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None

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

    applications: List[TopologyApplication] = Relationship(
        back_populates="services", link_model=TopologyServiceApplication
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
    email: Optional[str] = None
    slack: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None


class TopologyServiceInDto(TopologyServiceDtoBase):
    dependencies: dict[str, str] = {}  # dict of service it depends on : protocol


class TopologyServiceDependencyDto(BaseModel, extra="ignore"):
    serviceId: int
    serviceName: str
    protocol: Optional[str] = "unknown"


class TopologyApplicationDto(BaseModel, extra="ignore"):
    id: UUID
    name: str
    description: Optional[str] = None
    services: List[TopologyService] = Relationship(
        back_populates="applications", link_model="TopologyServiceApplication"
    )


class TopologyServiceDtoIn(BaseModel, extra="ignore"):
    id: int


class TopologyApplicationDtoIn(BaseModel, extra="ignore"):
    id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    services: List[TopologyServiceDtoIn] = []


class TopologyApplicationServiceDto(BaseModel, extra="ignore"):
    id: int
    name: str
    service: str

    @classmethod
    def from_orm(cls, service: "TopologyService") -> "TopologyApplicationServiceDto":
        return cls(
            id=service.id,
            name=service.display_name,
            service=service.service,
        )


class TopologyApplicationDtoOut(TopologyApplicationDto):
    services: List[TopologyApplicationServiceDto] = []

    @classmethod
    def from_orm(
        cls, application: "TopologyApplication"
    ) -> "TopologyApplicationDtoOut":
        return cls(
            id=application.id,
            name=application.name,
            description=application.description,
            services=[
                TopologyApplicationServiceDto.from_orm(service)
                for service in application.services
            ],
        )


class TopologyServiceDtoOut(TopologyServiceDtoBase):
    id: int
    dependencies: List[TopologyServiceDependencyDto]
    application_ids: List[UUID]
    updated_at: Optional[datetime]

    @classmethod
    def from_orm(
        cls, service: "TopologyService", application_ids: List[UUID]
    ) -> "TopologyServiceDtoOut":
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
            email=service.email,
            slack=service.slack,
            ip_address=service.ip_address,
            mac_address=service.mac_address,
            manufacturer=service.manufacturer,
            category=service.category,
            dependencies=[
                TopologyServiceDependencyDto(
                    serviceId=dep.depends_on_service_id,
                    protocol=dep.protocol,
                    serviceName=dep.dependent_service.service,
                )
                for dep in service.dependencies
            ],
            application_ids=application_ids,
            updated_at=service.updated_at,
        )
