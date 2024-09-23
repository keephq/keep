import logging
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import joinedload, selectinload

from sqlmodel import Session, select

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


class TopologiesService:
    @staticmethod
    def get_all_topology_data(
        tenant_id: str,
        session: Session,
        provider_id: Optional[str] = None,
        service: Optional[str] = None,
        environment: Optional[str] = None,
        include_empty_deps: Optional[bool] = False,
    ) -> List[TopologyServiceDtoOut]:
        query = select(TopologyService).where(TopologyService.tenant_id == tenant_id)

        # @tb: let's filter by service only for now and take care of it when we handle multiple
        # services and environments and cmdbs
        # the idea is that we show the service topology regardless of the underlying provider/env
        if service is not None:
            query = query.where(
                TopologyService.service == service,
            )

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
        service_ids = [service.id for service in services]
        application_service_query = (
            select(TopologyServiceApplication)
            .where(TopologyServiceApplication.service_id.in_(service_ids))
            .group_by(TopologyServiceApplication.service_id)
        )
        application_service_results = session.exec(application_service_query).all()

        # Create a dictionary mapping service IDs to application IDs
        service_to_app_ids = {}
        for result in application_service_results:
            if result.service_id not in service_to_app_ids:
                service_to_app_ids[result.service_id] = []
            service_to_app_ids[result.service_id].append(result.application_id)

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
            except Exception as e:
                logger.error(
                    f"Error converting application to DTO: {str(e)}",
                    extra={"application_id": application.id, "error": str(e)},
                )

        return result

    @staticmethod
    def create_application_by_tenant_id(
        tenant_id: str, application: TopologyApplicationDtoIn, session: Session
    ) -> TopologyApplicationDtoOut:
        new_application = TopologyApplication(
            tenant_id=tenant_id,
            name=application.name,
            description=application.description,
        )
        session.add(new_application)
        session.flush()  # This assigns an ID to new_application

        service_ids = [service.id for service in application.services]
        # Fetch existing services
        existing_services = session.exec(
            select(TopologyService)
            .where(TopologyService.tenant_id == tenant_id)
            .where(TopologyService.id.in_(service_ids))
        ).all()

        # Create TopologyServiceApplication links
        for service in existing_services:
            link = TopologyServiceApplication(
                service_id=service.id, application_id=new_application.id
            )
            session.add(link)

        session.commit()

        session.expire(new_application, ["services"])

        return TopologyApplicationDtoOut.from_orm(new_application)

    @staticmethod
    def update_application_by_id(
        tenant_id: str,
        application_id: str,
        application: TopologyApplicationDtoIn,
        session: Session,
    ) -> TopologyApplicationDtoOut:
        application_db = session.exec(
            select(TopologyApplication)
            .where(TopologyApplication.tenant_id == tenant_id)
            .where(TopologyApplication.id == application_id)
        ).first()
        if not application_db:
            raise HTTPException(status_code=404, detail="Application not found")

        application_db.name = application.name
        application_db.description = application.description

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

        new_links = [
            TopologyServiceApplication(
                service_id=service_id, application_id=application_id
            )
            for service_id in new_service_ids - existing_service_ids
        ]
        session.add_all(new_links)

        session.commit()
        session.refresh(application_db)
        return TopologyApplicationDtoOut.from_orm(application_db)

    @staticmethod
    def delete_application_by_id(tenant_id: str, application_id: str, session: Session):
        application = session.exec(
            select(TopologyApplication)
            .where(TopologyApplication.tenant_id == tenant_id)
            .where(TopologyApplication.id == application_id)
        ).first()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        session.delete(application)
        session.commit()
        return None
