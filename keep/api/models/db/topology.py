from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, PrimaryKeyConstraint, ForeignKeyConstraint
from sqlmodel import JSON, Column, Field, Relationship, SQLModel, func


class TopologyServiceApplication(SQLModel, table=True):
    tenant_id: str = Field(sa_column=Column(ForeignKey("tenant.id"), primary_key=True))
    service_id: int = Field(primary_key=True)
    application_id: UUID = Field(primary_key=True)

    service: "TopologyService" = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "and_(TopologyService.id == TopologyServiceApplication.service_id,"
                           "TopologyService.tenant_id == TopologyServiceApplication.tenant_id)",
            "viewonly": "True",
        },
    )
    application: "TopologyApplication" = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "and_(TopologyApplication.id == TopologyServiceApplication.application_id,"
                           "TopologyService.tenant_id == TopologyServiceApplication.tenant_id)",
            "viewonly": "True",
        },
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ['service_id', 'tenant_id'],
            ['topologyservice.id', 'topologyservice.tenant_id'],
        ),
        ForeignKeyConstraint(
            ['application_id', 'tenant_id'],
            ['topologyapplication.id', 'topologyapplication.tenant_id'],
        ),
    )


class TopologyApplication(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(sa_column=Column(ForeignKey("tenant.id"), primary_key=True))
    name: str
    description: str = Field(default_factory=str)
    repository: str = Field(default_factory=str)
    services: List["TopologyService"] = Relationship(
        back_populates="applications", link_model=TopologyServiceApplication
    )


class TopologyService(SQLModel, table=True):
    id: int
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
    namespace: Optional[str] = None
    is_manual: Optional[bool] = False

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
            "foreign_keys": "[TopologyServiceDependency.service_id]",
            "cascade": "all, delete-orphan",
        },
    )

    applications: List[TopologyApplication] = Relationship(
        back_populates="services", link_model=TopologyServiceApplication
    )

    __table_args__ = (
        PrimaryKeyConstraint("id", "tenant_id"),  # Composite PK
    )

    class Config:
        orm_mode = True
        unique_together = [["id", "tenant_id"], ["tenant_id", "service", "environment", "source_provider_id"]]


class TopologyServiceDependency(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(sa_column=Column(ForeignKey("tenant.id")))
    service_id: int
    depends_on_service_id: int
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

    __table_args__ = (
        PrimaryKeyConstraint("id", "tenant_id"),  # Composite PK
        ForeignKeyConstraint(
            ['service_id', 'tenant_id'],
            ['topologyservice.id', 'topologyservice.tenant_id'],
            "topologyservicedependency_service_id_tenant_id_fkey"
        ),
        ForeignKeyConstraint(
            ['depends_on_service_id', 'tenant_id'],
            ['topologyservice.id', 'topologyservice.tenant_id'],
            "topologyservicedependency_depends_on_service_id_tenant_id_fkey"
        ),
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
    namespace: Optional[str] = None
    is_manual: Optional[bool] = False


class TopologyServiceInDto(TopologyServiceDtoBase):
    dependencies: dict[str, str] = {}  # dict of service it depends on : protocol
    application_relations: Optional[dict[UUID, str]] = (
        None  # An option field, pass it in the form of {application_id_1: application_name_1, application_id_2: application_name_2, ...} tha t the service belongs to, the process_topology function handles the creation/updation of the application
    )


class TopologyServiceDependencyDto(BaseModel, extra="ignore"):
    id: str | UUID
    serviceId: str
    serviceName: str
    protocol: Optional[str] = "unknown"

    @classmethod
    def from_orm(cls, db_dependency: TopologyServiceDependency):
        return TopologyServiceDependencyDto(
            id=db_dependency.id,
            serviceId=str(db_dependency.depends_on_service_id),
            protocol=db_dependency.protocol,
            serviceName=db_dependency.dependent_service.service,
        )


class TopologyApplicationDto(BaseModel, extra="ignore"):
    id: UUID
    name: str
    description: Optional[str] = None
    repository: Optional[str] = None
    services: List[TopologyService] = Relationship(
        back_populates="applications", link_model="TopologyServiceApplication"
    )


class TopologyServiceDtoIn(BaseModel, extra="ignore"):
    id: int


class TopologyApplicationDtoIn(BaseModel, extra="ignore"):
    id: Optional[UUID] = None
    name: str
    description: str = ""
    repository: str = ""
    services: List[TopologyServiceDtoIn] = []


class TopologyApplicationServiceDto(BaseModel, extra="ignore"):
    id: str
    name: str
    service: str

    @classmethod
    def from_orm(cls, service: "TopologyService") -> "TopologyApplicationServiceDto":
        return cls(
            id=str(service.id),
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
            repository=application.repository,
            services=[
                TopologyApplicationServiceDto.from_orm(service)
                for service in application.services
            ],
        )


class TopologyServiceDtoOut(TopologyServiceDtoBase):
    id: str
    dependencies: List[TopologyServiceDependencyDto]
    application_ids: List[UUID]
    updated_at: Optional[datetime]

    @classmethod
    def from_orm(
        cls, service: "TopologyService", application_ids: List[UUID]
    ) -> "TopologyServiceDtoOut":
        return cls(
            id=str(service.id),
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
                    id=dep.id,
                    serviceId=str(dep.depends_on_service_id),
                    protocol=dep.protocol,
                    serviceName=dep.dependent_service.service,
                )
                for dep in service.dependencies
            ],
            application_ids=application_ids,
            updated_at=service.updated_at,
            namespace=service.namespace,
            is_manual=service.is_manual if service.is_manual is not None else False,
        )


class TopologyServiceCreateRequestDTO(BaseModel, extra="ignore"):
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
    namespace: Optional[str] = None


class TopologyServiceUpdateRequestDTO(TopologyServiceCreateRequestDTO, extra="ignore"):
    id: int


class TopologyServiceDependencyCreateRequestDto(BaseModel, extra="ignore"):
    service_id: int
    depends_on_service_id: int
    protocol: Optional[str] = "unknown"


class TopologyServiceDependencyUpdateRequestDto(
    TopologyServiceDependencyCreateRequestDto, extra="ignore"
):
    service_id: Optional[int]
    depends_on_service_id: Optional[int]
    id: int


class DeleteServicesRequest(BaseModel, extra="ignore"):
    service_ids: List[int]


class TopologyServiceYAML(TopologyServiceCreateRequestDTO, extra="ignore"):
    id: int
    source_provider_id: Optional[str] = None
    is_manual: Optional[bool] = None
