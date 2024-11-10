import logging

from arq import Retry

from keep.api.core.db import (
    create_incident_from_dto,
    get_incident_by_fingerprint,
    get_incident_by_id,
    update_incident_from_dto_by_id,
)
from keep.api.models.alert import IncidentDto

TIMES_TO_RETRY_JOB = 5  # the number of times to retry the job in case of failure
logger = logging.getLogger(__name__)


def process_incident(
    ctx: dict,
    tenant_id: str,
    provider_id: str | None,
    provider_type: str,
    incidents: IncidentDto | list[IncidentDto],
    trace_id: str | None = None,
):
    extra = {
        "tenant_id": tenant_id,
        "provider_id": provider_id,
        "provider_type": provider_type,
        "trace_id": trace_id,
    }

    if isinstance(incidents, IncidentDto):
        incidents = [incidents]

    logger.info(f"Processing {len(incidents)} incidents", extra=extra)

    if logger.getEffectiveLevel() == logging.DEBUG:
        # Lets log the incidents in debug mode
        extra["incident"] = [i.dict() for i in incidents]

    try:
        for incident in incidents:
            logger.info(
                f"Processing incident: {incident.id}",
                extra={**extra, "fingerprint": incident.fingerprint},
            )

            incident_from_db = get_incident_by_id(
                tenant_id=tenant_id, incident_id=incident.id
            )

            # Try to get by fingerprint if no incident was found by id
            if incident_from_db is None and incident.fingerprint:
                incident_from_db = get_incident_by_fingerprint(
                    tenant_id=tenant_id, fingerprint=incident.fingerprint
                )

            if incident_from_db:
                logger.info(
                    f"Updating incident: {incident.id}",
                    extra={**extra, "fingerprint": incident.fingerprint},
                )
                update_incident_from_dto_by_id(
                    tenant_id=tenant_id,
                    incident_id=incident_from_db.id,
                    updated_incident_dto=incident,
                )
                logger.info(
                    f"Updated incident: {incident.id}",
                    extra={**extra, "fingerprint": incident.fingerprint},
                )
            else:
                logger.info(
                    f"Creating incident: {incident.id}",
                    extra={**extra, "fingerprint": incident.fingerprint},
                )
                create_incident_from_dto(
                    tenant_id=tenant_id,
                    incident_dto=incident,
                )
                logger.info(
                    f"Created incident: {incident.id}",
                    extra={**extra, "fingerprint": incident.fingerprint},
                )
            logger.info("Processed incident", extra=extra)
        logger.info("Processed all incidents", extra=extra)
    except Exception:
        logger.exception(
            "Error processing incidents",
            extra=extra,
        )

        # Retrying only if context is present (running the job in arq worker)
        if bool(ctx):
            raise Retry(defer=ctx["job_try"] * TIMES_TO_RETRY_JOB)


async def async_process_incident(*args, **kwargs):
    return process_incident(*args, **kwargs)
