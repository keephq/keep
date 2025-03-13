import logging

from arq import Retry
from sqlmodel import Session

from keep.api.bl.incidents_bl import IncidentBl
from keep.api.core.db import (
    get_incident_by_fingerprint,
    get_incident_by_id,
    engine,
)
from keep.api.models.incident import IncidentDto
from keep.api.tasks.process_event_task import process_event

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

    with Session(engine) as session:

        if ctx and isinstance(ctx, dict):
            extra["job_try"] = ctx.get("job_try", 0)
            extra["job_id"] = ctx.get("job_id", None)

        if isinstance(incidents, IncidentDto):
            incidents = [incidents]

        logger.info(f"Processing {len(incidents)} incidents", extra=extra)

        if logger.getEffectiveLevel() == logging.DEBUG:
            # Lets log the incidents in debug mode
            extra["incident"] = [i.dict() for i in incidents]

        incident_bl = IncidentBl(tenant_id, session)

        try:
            for incident in incidents:
                logger.info(
                    f"Processing incident: {incident.id}",
                    extra={**extra, "fingerprint": incident.fingerprint},
                )

                incident_from_db = get_incident_by_id(
                    tenant_id=tenant_id, incident_id=incident.id, session=session
                )

                # Try to get by fingerprint if no incident was found by id
                if incident_from_db is None and incident.fingerprint:
                    incident_from_db = get_incident_by_fingerprint(
                        tenant_id=tenant_id, fingerprint=incident.fingerprint, session=session
                    )

                if incident_from_db:
                    logger.info(
                        f"Updating incident: {incident.id}",
                        extra={**extra, "fingerprint": incident.fingerprint},
                    )
                    incident_from_db = incident_bl.update_incident(
                        incident_id=incident_from_db.id,
                        updated_incident_dto=incident,
                        generated_by_ai=False,
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
                    incident_from_db = incident_bl.create_incident(
                        incident_dto=incident,
                    )
                    logger.info(
                        f"Created incident: {incident.id}",
                        extra={**extra, "fingerprint": incident.fingerprint},
                    )

                try:
                    if incident.alerts:
                        logger.info("Adding incident alerts", extra=extra)
                        processed_alerts = process_event(
                            {},
                            tenant_id,
                            provider_type,
                            provider_id,
                            None,
                            None,
                            trace_id,
                            incident.alerts,
                        )
                        if processed_alerts:
                            incident_bl.sync_add_alerts_to_incident(
                                incident_from_db.id,
                                [
                                    processed_alert.fingerprint
                                    for processed_alert in processed_alerts
                                ],
                                # Because the incident was created with the alerts count, we need to override it
                                # otherwise it will be the sum of the previous count + the newly attached alerts count
                                override_count=True,
                            )
                            logger.info("Added incident alerts", extra=extra)
                        else:
                            logger.info(
                                "No alerts to add to incident, probably deduplicated",
                                extra=extra,
                            )
                except Exception:
                    logger.exception("Error adding incident alerts", extra=extra)
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
