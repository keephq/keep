import json
import logging
from typing import List, Optional
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import Session, select

from keep.api.core.db_utils import get_aggreated_field
from keep.api.models.db.topology import (
    TopologyApplication,
    TopologyApplicationDtoIn,
    TopologyApplicationDtoOut,
    TopologyService,
    TopologyServiceApplication,
    TopologyServiceDependency,
    TopologyServiceDtoOut,
)

logger = logging.getLogger(__name__)


class TopologyException(Exception):
    """Base exception for topology-related errors"""


class ApplicationParseException(TopologyException):
    """Raised when an application cannot be parsed"""


class ApplicationNotFoundException(TopologyException):
    """Raised when an application is not found"""


class InvalidApplicationDataException(TopologyException):
    """Raised when application data is invalid"""


class ServiceNotFoundException(TopologyException):
    """Raised when a service is not found"""


def get_service_application_ids_dict(
    session: Session, service_ids: List[int]
) -> dict[int, List[UUID]]:
    # TODO: add proper types
    query = (
        select(
            TopologyServiceApplication.service_id,
            get_aggreated_field(
                session,
                TopologyServiceApplication.application_id,  # type: ignore
                "application_ids",
            ),
        )
        .where(TopologyServiceApplication.service_id.in_(service_ids))
        .group_by(TopologyServiceApplication.service_id)
    )
    results = session.exec(query).all()
    dialect_name = session.bind.dialect.name if session.bind else ""
    result = {}
    if session.bind is None:
        raise ValueError("Session is not bound to a database")
    for application_id, service_ids in results:
        if dialect_name == "postgresql":
            # PostgreSQL returns a list of UUIDs
            pass
        elif dialect_name == "mysql":
            # MySQL returns a JSON string, so we need to parse it
            service_ids = json.loads(service_ids)
        elif dialect_name == "sqlite":
            # SQLite returns a comma-separated string
            service_ids = [UUID(id) for id in service_ids.split(",")]
        else:
            if service_ids and isinstance(service_ids[0], UUID):
                # If it's already a list of UUIDs (like in PostgreSQL), use it as is
                pass
            else:
                # For any other case, try to convert to UUID
                service_ids = [UUID(str(id)) for id in service_ids]
        result[application_id] = service_ids

    return result


class TopologiesService:
    @staticmethod
    def get_all_topology_data(
        tenant_id: str,
        session: Session,
        provider_ids: Optional[str] = None,
        services: Optional[str] = None,
        environment: Optional[str] = None,
        include_empty_deps: Optional[bool] = False,
    ) -> List[TopologyServiceDtoOut]:
        query = select(TopologyService).where(TopologyService.tenant_id == tenant_id)

        # @tb: let's filter by service only for now and take care of it when we handle multiple
        # services and environments and cmdbs
        # the idea is that we show the service topology regardless of the underlying provider/env
        if services is not None:
            query = query.where(TopologyService.service.in_(services.split(",")))

            service_instance = session.exec(query).first()
            if not service_instance:
                return []

            services = session.exec(
                select(TopologyServiceDependency)
                .where(
                    TopologyServiceDependency.depends_on_service_id
                    == service_instance.id
                )
                .options(joinedload(TopologyServiceDependency.service))
            ).all()
            services = [service_instance, *[service.service for service in services]]
        else:
            # Fetch services for the tenant
            services = session.exec(
                query.options(
                    selectinload(TopologyService.dependencies).selectinload(
                        TopologyServiceDependency.dependent_service
                    )
                )
            ).all()

        # Fetch application IDs for all services in a single query
        service_ids = [service.id for service in services if service.id is not None]
        service_to_app_ids = get_service_application_ids_dict(session, service_ids)

        logger.info(f"Service to app ids: {service_to_app_ids}")

        service_dtos = [
            TopologyServiceDtoOut.from_orm(
                service, application_ids=service_to_app_ids.get(service.id, [])
            )
            for service in services
            if service.dependencies or include_empty_deps
        ]

        return service_dtos

    @staticmethod
    def get_applications_by_tenant_id(
        tenant_id: str, session: Session
    ) -> List[TopologyApplicationDtoOut]:
        applications = session.exec(
            select(TopologyApplication).where(
                TopologyApplication.tenant_id == tenant_id
            )
        ).all()
        result = []
        for application in applications:
            try:
                app_dto = TopologyApplicationDtoOut.from_orm(application)
                result.append(app_dto)
            except ValidationError as e:
                logger.error(
                    f"Failed to parse application with id {application.id}: {e}"
                )
                raise ApplicationParseException(
                    f"Failed to parse application with id {application.id}"
                )
        return result

    @staticmethod
    def create_application_by_tenant_id(
        tenant_id: str, application: TopologyApplicationDtoIn, session: Session
    ) -> TopologyApplicationDtoOut:
        service_ids = [service.id for service in application.services]
        if not service_ids:
            raise InvalidApplicationDataException(
                "Application must have at least one service"
            )

        # Fetch existing services
        services_to_add = session.exec(
            select(TopologyService)
            .where(TopologyService.tenant_id == tenant_id)
            .where(TopologyService.id.in_(service_ids))
        ).all()
        if len(services_to_add) != len(service_ids):
            raise ServiceNotFoundException("One or more services not found")

        new_application = TopologyApplication(
            tenant_id=tenant_id,
            name=application.name,
            description=application.description,
        )

        # This will be true if we are pulling applications from a Provider
        if application.id:
            new_application.id = application.id

        session.add(new_application)
        session.flush()  # This assigns an ID to new_application

        # Create TopologyServiceApplication links
        new_links = [
            TopologyServiceApplication(
                service_id=service.id, application_id=new_application.id
            )
            for service in services_to_add
            if service.id
        ]

        session.add_all(new_links)
        session.commit()

        session.expire(new_application, ["services"])

        return TopologyApplicationDtoOut.from_orm(new_application)

    @staticmethod
    def update_application_by_id(
        tenant_id: str,
        application_id: UUID,
        application: TopologyApplicationDtoIn,
        session: Session,
        existing_application: Optional[TopologyApplication] = None,
    ) -> TopologyApplicationDtoOut:
        if existing_application:
            application_db = existing_application
        else:
            application_db = session.exec(
                select(TopologyApplication)
                .where(TopologyApplication.tenant_id == tenant_id)
                .where(TopologyApplication.id == application_id)
            ).first()
        if not application_db:
            raise ApplicationNotFoundException(
                f"Application with id {application_id} not found"
            )

        application_db.name = application.name
        application_db.description = application.description
        application_db.repository = application.repository

        new_service_ids = set(service.id for service in application.services)

        # Remove existing links not in the update request
        session.query(TopologyServiceApplication).where(
            TopologyServiceApplication.application_id == application_id
        ).where(TopologyServiceApplication.service_id.not_in(new_service_ids)).delete()

        # Add new links
        existing_links = session.exec(
            select(TopologyServiceApplication.service_id).where(
                TopologyServiceApplication.application_id == application_id
            )
        ).all()
        existing_service_ids = set(existing_links)

        services_to_add_ids = new_service_ids - existing_service_ids

        # Fetch existing services
        services_to_add = session.exec(
            select(TopologyService)
            .where(TopologyService.tenant_id == tenant_id)
            .where(TopologyService.id.in_(services_to_add_ids))
        ).all()

        if len(services_to_add) != len(services_to_add_ids):
            raise ServiceNotFoundException("One or more services not found")

        new_links = [
            TopologyServiceApplication(
                service_id=service.id, application_id=application_id
            )
            for service in services_to_add
            if service.id
        ]
        session.add_all(new_links)

        session.commit()
        session.refresh(application_db)
        return TopologyApplicationDtoOut.from_orm(application_db)

    @staticmethod
    def create_or_update_application(
        tenant_id: str,
        application: TopologyApplicationDtoIn,
        session: Session,
    ) -> TopologyApplicationDtoOut:
        # Check if an application with the same name already exists for the tenant
        existing_application = session.exec(
            select(TopologyApplication)
            .where(TopologyApplication.tenant_id == tenant_id)
            .where(TopologyApplication.id == application.id)
        ).first()

        if existing_application:
            # If the application exists, update it
            return TopologiesService.update_application_by_id(
                tenant_id=tenant_id,
                application_id=existing_application.id,
                application=application,
                session=session,
                existing_application=existing_application,
            )
        else:
            # If the application doesn't exist, create it
            return TopologiesService.create_application_by_tenant_id(
                tenant_id=tenant_id,
                application=application,
                session=session,
            )

    @staticmethod
    def delete_application_by_id(
        tenant_id: str, application_id: UUID, session: Session
    ):
        # Validate that application_id is a valid UUID
        application = session.exec(
            select(TopologyApplication)
            .where(TopologyApplication.tenant_id == tenant_id)
            .where(TopologyApplication.id == application_id)
        ).first()
        if not application:
            raise ApplicationNotFoundException(
                f"Application with id {application_id} not found"
            )
        session.delete(application)
        session.commit()
        return None
