import copy
import logging

from keep.api.core.db import get_session_sync
from keep.api.models.db.topology import (
    TopologyService,
    TopologyServiceDependency,
    TopologyServiceInDto,
)

logger = logging.getLogger(__name__)

TIMES_TO_RETRY_JOB = 5  # the number of times to retry the job in case of failure


def process_topology(
    tenant_id: str, topology_data: list[TopologyServiceInDto], provider_id: str
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

    # Then create the dependencies
    for service in topology_data:
        for dependency in service.dependencies:
            session.add(
                TopologyServiceDependency(
                    service_id=service_to_keep_service_id_map[service.service],
                    depends_on_service_id=service_to_keep_service_id_map[dependency],
                    protocol=service.dependencies[dependency],
                )
            )

    session.commit()

    try:
        session.close()
    except Exception as e:
        logger.warning(
            "Failed to close session",
            extra={**extra, "error": str(e)},
        )

    logger.info(
        "Created new topology data",
        extra=extra,
    )


async def async_process_topology(*args, **kwargs):
    return process_topology(*args, **kwargs)
