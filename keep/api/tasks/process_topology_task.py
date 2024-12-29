import copy
import logging

from keep.api.core.db import get_session_sync
from keep.api.core.dependencies import get_pusher_client
from keep.api.models.db.topology import (
    TopologyService,
    TopologyServiceDependency,
    TopologyServiceInDto,
    TopologyApplicationDtoIn,
    TopologyServiceDtoIn,
)
from keep.topologies.topologies_service import TopologiesService

logger = logging.getLogger(__name__)

TIMES_TO_RETRY_JOB = 5  # the number of times to retry the job in case of failure


def process_topology(
    tenant_id: str,
    topology_data: list[TopologyServiceInDto],
    provider_id: str,
    provider_type: str,
):
    extra = {"provider_id": provider_id, "tenant_id": tenant_id}
    if not topology_data:
        logger.info(
            "No topology data to process",
            extra=extra,
        )
        return

    logger.info("Processing topology data", extra=extra)
    session = get_session_sync()

    try:
        logger.info(
            "Deleting existing topology data",
            extra=extra,
        )

        session.query(TopologyService).filter(
            TopologyService.source_provider_id == provider_id,
            TopologyService.tenant_id == tenant_id,
        ).delete()

        session.commit()
        logger.info(
            "Deleted existing topology data",
            extra=extra,
        )
    except Exception:
        logger.exception(
            "Failed to delete existing topology data",
            extra=extra,
        )
        raise

    logger.info(
        "Creating new topology data",
        extra={"provider_id": provider_id, "tenant_id": tenant_id},
    )
    service_to_keep_service_id_map = {}
    # First create the services so we have ids
    for service in topology_data:
        service_copy = copy.deepcopy(service.dict())
        service_copy.pop("dependencies")
        db_service = TopologyService(**service_copy, tenant_id=tenant_id)
        session.add(db_service)
        session.flush()
        service_to_keep_service_id_map[service.service] = db_service.id

    application_to_services = {}
    application_to_name = {}

    # Then create the dependencies
    for service in topology_data:

        # Group all services by application (this is for processing application related data in the next step)
        if service.application_relations is not None:
            service_id = service_to_keep_service_id_map.get(service.service)
            for application_id in service.application_relations:

                application_to_name[application_id] = service.application_relations[
                    application_id
                ]

                if application_id not in application_to_services:
                    application_to_services[application_id] = [service_id]
                else:
                    application_to_services[application_id].append(service_id)

        for dependency in service.dependencies:
            service_id = service_to_keep_service_id_map.get(service.service)
            depends_on_service_id = service_to_keep_service_id_map.get(dependency)
            if not service_id or not depends_on_service_id:
                logger.debug(
                    "Found a dangling service, skipping",
                    extra={"service": service.service, "dependency": dependency},
                )
                continue
            session.add(
                TopologyServiceDependency(
                    service_id=service_id,
                    depends_on_service_id=depends_on_service_id,
                    protocol=service.dependencies.get(dependency, "unknown"),
                )
            )

    session.commit()

    # Now create or update the application
    for application_id in application_to_services:
        TopologiesService.create_or_update_application(
            tenant_id=tenant_id,
            application=TopologyApplicationDtoIn(
                id=application_id,
                name=application_to_name[application_id],
                services=[
                    TopologyServiceDtoIn(id=service_id)
                    for service_id in application_to_services[application_id]
                ],
            ),
            session=session,
        )

    try:
        session.close()
    except Exception as e:
        logger.warning(
            "Failed to close session",
            extra={**extra, "error": str(e)},
        )

    try:
        pusher_client = get_pusher_client()
        if pusher_client:
            pusher_client.trigger(
                f"private-{tenant_id}",
                "topology-update",
                {"providerId": provider_id, "providerType": provider_type},
            )
    except Exception:
        logger.exception("Failed to push topology update to the client")

    logger.info(
        "Created new topology data",
        extra=extra,
    )


async def async_process_topology(*args, **kwargs):
    return process_topology(*args, **kwargs)
