import csv
import hashlib
import io
import json
import logging
import uuid
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import and_, exists, insert, or_
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import Session, select

from keep.api.core.db_utils import get_aggreated_field
from keep.api.models.db.topology import (
    TopologyApplication,
    TopologyApplicationDtoIn,
    TopologyApplicationDtoOut,
    TopologyService,
    TopologyServiceApplication,
    TopologyServiceCreateRequestDTO,
    TopologyServiceDependency,
    TopologyServiceDependencyCreateRequestDto,
    TopologyServiceDependencyDto,
    TopologyServiceDependencyUpdateRequestDto,
    TopologyServiceDtoOut,
    TopologyServiceUpdateRequestDTO,
    TopologyServiceYAML,
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


class ServiceNotManualException(TopologyException):
    """Raised when a service is not manual"""


class DependencyNotFoundException(TopologyException):
    """Raised when a dependency is not found"""


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


def validate_non_manual_exists(
    service_ids: list[int], session: Session, tenant_id: str
) -> bool:
    non_manual_exists = session.query(
        exists()
        .where(TopologyService.id.in_(service_ids))
        .where(TopologyService.tenant_id == tenant_id)
        .where(TopologyService.is_manual.isnot(True))
    ).scalar()

    return non_manual_exists


class TopologiesService:
    @staticmethod
    def get_topology_services(
        tenant_id: str,
        session: Session,
        provider_ids: Optional[str] = None,
        services: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> list[TopologyService]:
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
        return services

    @staticmethod
    def get_all_topology_data(
        tenant_id: str,
        session: Session,
        provider_ids: Optional[str] = None,
        services: Optional[str] = None,
        environment: Optional[str] = None,
        include_empty_deps: Optional[bool] = False,
    ) -> List[TopologyServiceDtoOut]:
        services = TopologiesService.get_topology_services(
            tenant_id, session, provider_ids, services, environment
        )

        # Fetch application IDs for all services in a single query
        service_ids = [service.id for service in services if service.id is not None]
        service_to_app_ids = get_service_application_ids_dict(session, service_ids)

        logger.info("Service to app ids")
        service_dtos = []
        for service in services:
            if include_empty_deps or service.dependencies:
                try:
                    service_dto = [
                        TopologyServiceDtoOut.from_orm(
                            service,
                            application_ids=service_to_app_ids.get(service.id, []),
                        )
                    ]
                    service_dtos.extend(service_dto)
                except Exception:
                    logger.exception(
                        "Failed to parse service with id",
                        extra={
                            "service_id": service.id,
                        },
                    )
                    raise ApplicationParseException(
                        f"Failed to parse service with id {service.id}"
                    )

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
    def create_applications_by_tenant_id(
        tenant_id: str, applications: List[TopologyApplicationDtoIn], session: Session
    ) -> None:
        """Creates multiple applications for a given tenant in a single transaction."""

        try:
            new_applications = []
            new_links = []

            for application in applications:
                service_ids = [service.id for service in application.services]
                if not service_ids:
                    raise InvalidApplicationDataException(
                        "Each application must have at least one service"
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

                if application.id:
                    new_application.id = application.id  # Preserve ID if provided

                session.add(new_application)
                new_applications.append(new_application)

            session.flush()  # Assigns IDs to new applications

            for new_application, application in zip(new_applications, applications):
                new_links.extend(
                    [
                        TopologyServiceApplication(
                            service_id=service.id, application_id=new_application.id
                        )
                        for service in application.services
                        if service.id
                    ]
                )

            session.add_all(new_links)
            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"Error while creating applications: {e}")
            raise e
        finally:
            session.close()

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

    @staticmethod
    def get_service_by_id(
        _id: int, tenant_id: str, session: Session
    ) -> TopologyService:
        return session.exec(
            select(TopologyService)
            .where(TopologyService.tenant_id == tenant_id)
            .where(TopologyService.id == _id)
        ).first()

    @staticmethod
    def get_dependency_by_id(_id: int, session: Session) -> TopologyServiceDependency:
        return session.exec(
            select(TopologyServiceDependency).where(TopologyServiceDependency.id == _id)
        ).first()

    @staticmethod
    def create_service(
        service: TopologyServiceCreateRequestDTO, tenant_id: str, session: Session
    ) -> TopologyService:
        """This function is used for creating services manually. services.is_manual=True"""

        try:
            # Setting is_manual to True since this service is created manually.
            db_service = TopologyService(
                **service.dict(), tenant_id=tenant_id, is_manual=True
            )
            session.add(db_service)
            session.commit()
            session.refresh(db_service)
            return db_service
        except Exception as e:
            session.rollback()
            logger.error(f"Error while creating/updating the services manually: {e}")
            raise e
        finally:
            session.close()

    @staticmethod
    def create_services(
        services: List[TopologyServiceYAML],
        tenant_id: str,
        session: Session,
    ) -> None:
        """Creates multiple services in a single transaction using modern bulk insert."""

        try:
            # Convert all services to dictionaries at once
            service_dicts = [
                {**service.dict(), "tenant_id": tenant_id} for service in services
            ]

            # Use modern SQLAlchemy 2.0 bulk insert approach
            logger.info(f"Bulk inserting {len(service_dicts)} services")
            import logging

            logging.basicConfig()
            logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)
            session.execute(insert(TopologyService), service_dicts)

            session.commit()
            logger.info(f"Successfully inserted {len(service_dicts)} services")

        except Exception as e:
            session.rollback()
            logger.error(f"Error while bulk creating services: {e}")
            raise e
        finally:
            session.close()

    @staticmethod
    def update_service(
        service: TopologyServiceUpdateRequestDTO, tenant_id: str, session: Session
    ) -> TopologyService:
        try:
            db_service: TopologyService = TopologiesService.get_service_by_id(
                _id=service.id, tenant_id=tenant_id, session=session
            )

            # Asserting that the service we're trying to update was created manually
            if not db_service.is_manual:
                raise ServiceNotManualException()

            service_dict = service.dict()
            if db_service is None:
                raise ServiceNotFoundException()
            else:  # We update it.
                for attr in service_dict:
                    if (
                        service_dict[attr] is not None
                        and db_service.__getattribute__(attr) != service_dict[attr]
                    ):
                        db_service.__setattr__(attr, service_dict[attr])
                session.commit()
                session.refresh(db_service)
                return db_service
        except Exception as e:
            session.rollback()
            logger.error(f"Error while updating the services manually: {e}")
            raise e
        finally:
            session.close()

    @staticmethod
    def delete_services(service_ids: list[int], tenant_id: str, session: Session):
        try:

            # Asserting that all the services that we are trying to delete were created manually, if this assertion
            # fails we do not proceed with deletion at all
            if validate_non_manual_exists(
                service_ids=service_ids,
                session=session,
                tenant_id=tenant_id,
            ):
                raise ServiceNotManualException()

            # Deleting all the dependencies first
            session.query(TopologyServiceDependency).filter(
                TopologyServiceDependency.service.has(
                    and_(
                        TopologyService.tenant_id == tenant_id,
                        or_(
                            TopologyServiceDependency.service_id.in_(service_ids),
                            TopologyServiceDependency.depends_on_service_id.in_(
                                service_ids
                            ),
                        ),
                    )
                )
            ).delete(synchronize_session=False)

            deleted_count = (
                session.query(TopologyService)
                .filter(
                    TopologyService.id.in_(service_ids),
                    TopologyService.tenant_id == tenant_id,
                )
                .delete(synchronize_session=False)  # Efficient batch delete
            )

            if deleted_count == 0:
                raise ServiceNotFoundException("No services found for the given IDs.")

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error while deleting services: {e}")
            raise e
        finally:
            session.close()

    @staticmethod
    def create_dependency(
        dependency: TopologyServiceDependencyCreateRequestDto,
        tenant_id: str,
        session: Session,
        enforce_manual: bool = True,
    ) -> TopologyServiceDependencyDto:
        try:
            # Enforcing is_manual on the service_id and depends_on_service_id
            if enforce_manual and validate_non_manual_exists(
                service_ids=[dependency.service_id, dependency.depends_on_service_id],
                session=session,
                tenant_id=tenant_id,
            ):
                raise ServiceNotManualException()

            db_dependency = TopologyServiceDependency(**dependency.dict())
            session.add(db_dependency)
            session.commit()
            session.refresh(db_dependency)
            return TopologyServiceDependencyDto.from_orm(db_dependency)
        except Exception as e:
            session.rollback()
            logger.error(f"Error while creating/updating the Dependency manually: {e}")
            raise e
        finally:
            session.close()

    @staticmethod
    def create_dependencies(
        dependencies: List[TopologyServiceDependencyCreateRequestDto],
        tenant_id: str,
        session: Session,
        enforce_manual: bool = True,
    ) -> None:
        """Creates multiple dependencies in a single transaction."""

        try:
            db_dependencies = []

            for dependency in dependencies:
                # Enforcing is_manual on the service_id and depends_on_service_id
                if enforce_manual and validate_non_manual_exists(
                    service_ids=[
                        dependency.service_id,
                        dependency.depends_on_service_id,
                    ],
                    session=session,
                    tenant_id=tenant_id,
                ):
                    raise ServiceNotManualException()

                db_dependency = TopologyServiceDependency(**dependency.dict())
                session.add(db_dependency)
                db_dependencies.append(db_dependency)

            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"Error while creating dependencies: {e}")
            raise e
        finally:
            session.close()

    @staticmethod
    def update_dependency(
        dependency: TopologyServiceDependencyUpdateRequestDto,
        session: Session,
        tenant_id: str,
    ) -> TopologyServiceDependencyDto:
        try:
            # Enforcing is_manual on the service_id and depends_on_service_id
            if validate_non_manual_exists(
                service_ids=[dependency.service_id, dependency.depends_on_service_id],
                session=session,
                tenant_id=tenant_id,
            ):
                raise ServiceNotManualException()

            db_dependency: TopologyServiceDependency = (
                TopologiesService.get_dependency_by_id(
                    _id=dependency.id, session=session
                )
            )
            service_dict = dependency.dict()
            if db_dependency is None:
                raise DependencyNotFoundException()
            else:  # We update it.
                for attr in service_dict:
                    if (
                        service_dict[attr] is not None
                        and db_dependency.__getattribute__(attr) != service_dict[attr]
                    ):
                        db_dependency.__setattr__(attr, service_dict[attr])
                session.commit()
                session.refresh(db_dependency)
                return TopologyServiceDependencyDto.from_orm(db_dependency)
        except Exception as e:
            session.rollback()
            logger.error(f"Error while updating the Dependency manually: {e}")
            raise e
        finally:
            session.close()

    @staticmethod
    def delete_dependency(dependency_id: int, session: Session, tenant_id: str):
        try:
            db_dependency: TopologyServiceDependency = (
                TopologiesService.get_dependency_by_id(
                    _id=dependency_id, session=session
                )
            )
            # Enforcing is_manual on the service_id and depends_on_service_id
            if validate_non_manual_exists(
                service_ids=[
                    db_dependency.service_id,
                    db_dependency.depends_on_service_id,
                ],
                session=session,
                tenant_id=tenant_id,
            ):
                raise ServiceNotManualException()

            if db_dependency is None:
                raise DependencyNotFoundException()
            session.delete(db_dependency)
            session.commit()
            return None
        except Exception as e:
            session.rollback()
            logger.error(f"Error while updating the Dependency manually: {e}")
            raise e
        finally:
            session.close()

    @staticmethod
    def clean_before_import(tenant_id: str, session: Session):
        """Removes all services and applications for a given tenant before importing a new topology."""
        try:
            # Delete all dependencies for this tenant
            session.query(TopologyServiceDependency).filter(
                TopologyServiceDependency.service.has(
                    TopologyService.tenant_id == tenant_id
                )
            ).delete(synchronize_session=False)

            # Delete all service-application links for this tenant
            session.query(TopologyServiceApplication).filter(
                TopologyServiceApplication.service.has(
                    TopologyService.tenant_id == tenant_id
                )
            ).delete(synchronize_session=False)

            # Delete all applications for this tenant
            session.query(TopologyApplication).filter(
                TopologyApplication.tenant_id == tenant_id
            ).delete(synchronize_session=False)

            # Delete all services for this tenant
            session.query(TopologyService).filter(
                TopologyService.tenant_id == tenant_id
            ).delete(synchronize_session=False)

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error during cleanup before import: {e}")
            raise e

    @staticmethod
    def import_to_db(
        topology_data: dict,
        session: Session,
        tenant_id: str,
        correlation_settings: Optional[Dict] = None,
    ):
        all_services: list[TopologyServiceYAML] = []
        all_applications: list[TopologyApplicationDtoIn] = []
        all_dependencies: list[TopologyServiceDependencyCreateRequestDto] = []
        try:
            # Clean existing data for the tenant before import
            TopologiesService.clean_before_import(tenant_id=tenant_id, session=session)

            for service in topology_data["services"]:
                all_services.append(TopologyServiceYAML(**service))

            for application in topology_data["applications"]:
                application["services"] = [
                    {"id": _id} for _id in application["services"]
                ]
                all_applications.append(TopologyApplicationDtoIn(**application))

            for dependency in topology_data["dependencies"]:
                all_dependencies.append(
                    TopologyServiceDependencyCreateRequestDto(**dependency)
                )

            # First create services
            logger.info(f"Creating {len(all_services)} services")
            TopologiesService.create_services(
                services=all_services,
                tenant_id=tenant_id,
                session=session,
            )

            # Then create specified applications
            logger.info(f"Creating {len(all_applications)} applications")
            TopologiesService.create_applications_by_tenant_id(
                tenant_id=tenant_id,
                applications=all_applications,
                session=session,
            )

            # And dependencies
            logger.info(f"Creating {len(all_dependencies)} dependencies")
            TopologiesService.create_dependencies(
                dependencies=all_dependencies,
                tenant_id=tenant_id,
                session=session,
                enforce_manual=False,
            )

            logger.info(f"Successfully imported topology for tenant {tenant_id}")

        except Exception as e:
            logger.error(f"Error while importing topology: {e}")
            session.rollback()
            raise e

    @staticmethod
    def _process_csv_to_topology(
        csv_content: bytes,
        field_mapping: Dict,
        topology_name: Optional[str] = None,
        correlation_settings: Optional[Dict] = None,
    ) -> Dict:
        """
        Process CSV content into topology data structure.

        Args:
            csv_content: CSV file content
            field_mapping: Mapping of CSV columns to topology fields
            topology_name: Optional name for the topology
            correlation_settings: Optional settings for auto-correlation of services

        Returns:
            Dictionary with services, applications, and dependencies
        """
        # Convert bytes to string and parse CSV
        csv_text = csv_content.decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(csv_text))

        # Create data structures for topology
        services_map = {}  # Maps service name to service id
        services = []
        applications_map = {}  # Maps application name to set of service ids
        dependencies = []

        # Extract required field names from mapping
        service_field = field_mapping.get("service")
        depends_on_field = field_mapping.get("dependsOn")
        display_name_field = field_mapping.get("displayName")
        environment_field = field_mapping.get("environment")
        description_field = field_mapping.get("description")
        application_field = field_mapping.get("application")
        protocol_field = field_mapping.get("protocol")
        team_field = field_mapping.get("team")
        email_field = field_mapping.get("email")
        slack_field = field_mapping.get("slack")
        category_field = field_mapping.get("category")

        # Validate required fields
        if not service_field or not depends_on_field:
            raise ValueError("Service and Dependencies fields must be mapped")

        # Process CSV rows
        for row_index, row in enumerate(csv_reader):
            source_service = row.get(service_field, "").strip()
            target_service = row.get(depends_on_field, "").strip()

            if not source_service or not target_service:
                continue  # Skip rows with missing service data

            # Process source service
            if source_service not in services_map:
                service_id = len(services) + 1  # Generate simple sequential ID
                services_map[source_service] = service_id

                # Create service object
                service = {
                    "id": service_id,
                    "service": source_service,
                    "display_name": (
                        row.get(display_name_field, source_service).strip()
                        if display_name_field
                        else source_service
                    ),
                    "environment": (
                        row.get(environment_field, "production").strip()
                        if environment_field
                        else "production"
                    ),
                    "description": (
                        row.get(description_field, "").strip()
                        if description_field
                        else ""
                    ),
                    "is_manual": True,
                }

                # Add optional fields if they exist in the mapping
                if team_field and row.get(team_field):
                    service["team"] = row.get(team_field).strip()
                if email_field and row.get(email_field):
                    service["email"] = row.get(email_field).strip()
                if slack_field and row.get(slack_field):
                    service["slack"] = row.get(slack_field).strip()
                if category_field and row.get(category_field):
                    service["category"] = row.get(category_field).strip()

                services.append(service)

            # Process target service
            if target_service not in services_map:
                service_id = len(services) + 1  # Generate simple sequential ID
                services_map[target_service] = service_id

                # Create service object with minimal information
                service = {
                    "id": service_id,
                    "service": target_service,
                    "display_name": target_service,
                    "environment": "production",
                    "description": "",
                    "is_manual": True,
                }
                services.append(service)

            # Create dependency
            dependency = {
                "service_id": services_map[source_service],
                "depends_on_service_id": services_map[target_service],
                "protocol": (
                    row.get(protocol_field, "HTTP").strip()
                    if protocol_field
                    else "HTTP"
                ),
            }
            if dependency not in dependencies:
                dependencies.append(dependency)
            else:
                logger.debug(f"Duplicate dependency found: {dependency}, skipping it.")

            # Process applications if field is mapped
            if application_field and row.get(application_field):
                apps = [
                    app.strip()
                    for app in row.get(application_field, "").split(",")
                    if app.strip()
                ]
                for app_name in apps:
                    if app_name not in applications_map:
                        applications_map[app_name] = set()
                    # Add both source and target services to the application
                    applications_map[app_name].add(services_map[source_service])
                    applications_map[app_name].add(services_map[target_service])

        # Create applications list with proper UUID IDs
        applications = []
        for app_name, service_ids in applications_map.items():
            # Generate proper UUID for application
            application_id = uuid.uuid4()

            application = {
                "id": str(application_id),  # Use UUID as string
                "name": app_name,
                "description": f"Application: {app_name}",
                "services": list(service_ids),
            }
            applications.append(application)

        # If no application mapping field is provided or no applications were found,
        # and correlation settings are provided, generate auto-correlated applications
        if (
            (not application_field or not applications)
            and correlation_settings
            and "depth" in correlation_settings
        ):
            # Build dependency graph for auto-correlation
            dependency_graph = {}

            # Create graph from services and dependencies
            for service in services:
                service_name = service["service"]
                if service_name not in dependency_graph:
                    dependency_graph[service_name] = set()

            for dependency in dependencies:
                source_id = dependency["service_id"]
                target_id = dependency["depends_on_service_id"]

                # Get service names from ids
                source_name = next(
                    (s["service"] for s in services if s["id"] == source_id), None
                )
                target_name = next(
                    (s["service"] for s in services if s["id"] == target_id), None
                )

                if source_name and target_name:
                    # Add bidirectional edges
                    if source_name not in dependency_graph:
                        dependency_graph[source_name] = set()
                    if target_name not in dependency_graph:
                        dependency_graph[target_name] = set()

                    dependency_graph[source_name].add(target_name)
                    dependency_graph[target_name].add(source_name)

            # Get correlation depth from settings
            correlation_depth = correlation_settings.get("depth", 5)

            # Find correlated service groups
            correlated_groups = TopologiesService._find_correlated_service_groups(
                dependency_graph, list(dependency_graph.keys()), correlation_depth
            )

            # Create applications for correlated groups
            for group_idx, service_group in enumerate(correlated_groups):
                # Generate a stable identifier for this service group
                sorted_services = sorted(service_group)
                interconnectivity_id = TopologiesService._generate_interconnectivity_id(
                    sorted_services
                )

                # Check if group services have IDs in our mapping
                group_service_ids = []
                for service_name in service_group:
                    if service_name in services_map:
                        group_service_ids.append(services_map[service_name])

                # Create application only if we have service IDs
                if group_service_ids:
                    # trim the services because they can be many services
                    services_desc = ", ".join(sorted_services[:3])
                    if len(sorted_services) > 3:
                        services_desc += f" and {len(sorted_services) - 3} more"
                    # Create application with a unique ID
                    description = f"Auto-generated application representing {len(sorted_services)} interconnected services: {services_desc}"
                    application = {
                        "id": interconnectivity_id,
                        "name": f"Auto-Correlated Services {group_idx+1}",
                        "description": description,
                        "services": group_service_ids,
                    }
                    applications.append(application)

        # Create the final topology data
        topology_data = {
            "name": topology_name or "Imported Topology",
            "services": services,
            "applications": applications,
            "dependencies": dependencies,
        }

        return topology_data

    @staticmethod
    def import_from_csv(
        csv_content: bytes,
        field_mapping: Dict,
        tenant_id: str,
        session: Session,
        topology_name: Optional[str] = None,
        correlation_settings: Optional[Dict] = None,
    ):
        """
        Import topology data from CSV content.

        Args:
            csv_content: Raw CSV file content
            field_mapping: Mapping between CSV columns and topology fields
            tenant_id: Tenant ID for which to import the topology
            session: Database session
            topology_name: Optional name for the topology
            correlation_settings: Optional settings for auto-correlation of services
        """
        try:
            # Process CSV to topology data structure
            topology_data = TopologiesService._process_csv_to_topology(
                csv_content, field_mapping, topology_name, correlation_settings
            )

            # Import processed data to the database
            TopologiesService.import_to_db(
                topology_data,
                session,
                tenant_id,
                None,  # No need to pass correlation_settings here since auto-correlation is done in _process_csv_to_topology
            )

        except Exception as e:
            logger.error(f"Error during CSV import: {e}")
            session.rollback()
            raise e

    @staticmethod
    def _build_dependency_graph(
        topology_data: List[TopologyServiceDtoOut],
    ) -> Dict[str, Set[str]]:
        """
        Build a graph representation of service dependencies.
        Returns a dict where keys are service names and values are sets of dependent services.
        """
        graph = defaultdict(set)

        # Map service IDs to service names for lookup
        service_id_to_name = {}

        for service in topology_data:
            service_id_to_name[str(service.id)] = service.service
            # Initialize entry for this service (even if it has no dependencies)
            if service.service not in graph:
                graph[service.service] = set()

        # Add dependencies to the graph
        for service in topology_data:
            source_service_name = service.service

            # Skip if service has no dependencies attribute or it's None
            if not hasattr(service, "dependencies") or service.dependencies is None:
                continue

            # Process each dependency
            for dependency in service.dependencies:
                # Skip null dependencies
                if dependency is None:
                    continue

                # Skip if dependency doesn't have required attributes
                if not hasattr(dependency, "serviceId") or not hasattr(
                    dependency, "serviceName"
                ):
                    continue

                # The source service is the current service
                # The destination service is identified by the dependency.serviceId
                dest_service_id = str(dependency.serviceId)

                # Look up the destination service name
                if dest_service_id in service_id_to_name:
                    dest_service_name = service_id_to_name[dest_service_id]

                    # Add bidirectional edges
                    graph[source_service_name].add(dest_service_name)
                    graph[dest_service_name].add(source_service_name)
                else:
                    # Use serviceName as fallback
                    graph[source_service_name].add(dependency.serviceName)
                    graph[dependency.serviceName].add(source_service_name)

        return graph

    @staticmethod
    def _find_correlated_service_groups(
        dependency_graph: Dict[str, Set[str]],
        services_list: List[str],
        max_depth: int,
    ) -> List[Set[str]]:
        """
        Find connected components (groups of services connected within max_depth).
        Each service will appear in only one group.
        """
        visited = set()
        correlated_groups = []

        for service in services_list:
            if service in visited:
                continue

            # Start a new group
            group = set()
            queue = deque([(service, 0)])  # (service, depth)
            visited.add(service)
            group.add(service)

            # BFS within max_depth
            while queue:
                current, depth = queue.popleft()

                if depth >= max_depth:
                    continue

                for neighbor in dependency_graph.get(current, set()):
                    if neighbor not in visited and neighbor in services_list:
                        visited.add(neighbor)
                        group.add(neighbor)
                        queue.append((neighbor, depth + 1))

            correlated_groups.append(group)

        return correlated_groups

    @staticmethod
    def _find_connected_services(
        graph: Dict[str, Set[str]],
        start_service: str,
        max_depth: int,
        services_list: List[str],
    ) -> Set[str]:
        """
        BFS to find all services connected to start_service within max_depth.
        """
        connected = {start_service}
        queue = deque([(start_service, 0)])  # (service, depth)
        visited = {start_service}

        while queue:
            current, depth = queue.popleft()

            # If we reached max depth, don't explore further
            if depth >= max_depth:
                continue

            for neighbor in graph.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)

                    # Only include services in the allowed list
                    if neighbor in services_list:
                        connected.add(neighbor)

                    # Enqueue neighbor for further exploration
                    queue.append((neighbor, depth + 1))

        return connected

    @staticmethod
    def _generate_interconnectivity_id(service_group: List[str]) -> str:
        """
        Generate a stable identifier for a group of interconnected services.
        This ensures that the same services will always get the same ID.

        Args:
            service_group: A list of service names

        Returns:
            A string UUID representation for the service group
        """
        # Sort to ensure consistent ordering
        sorted_services = sorted(service_group)
        # Join with a delimiter that won't appear in service names
        service_string = "|".join(sorted_services)
        # Use a hash function for a shorter representation
        # We need to make it a proper UUID
        md5_hash = hashlib.md5(service_string.encode()).hexdigest()
        # Format as UUID - take first 32 chars and insert hyphens
        return f"{md5_hash[:8]}-{md5_hash[8:12]}-{md5_hash[12:16]}-{md5_hash[16:20]}-{md5_hash[20:32]}"
