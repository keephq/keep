import logging

from keep.api.core.db import create_incident_from_dto, get_session_sync
from keep.api.models.alert import IncidentDto
from keep.api.models.db.alert import Incident

logger = logging.getLogger(__name__)

TIMES_TO_RETRY_JOB = 5  # the number of times to retry the job in case of failure


def process_incidents(tenant_id: str, incidents: list[IncidentDto]):
    if not incidents:
        return

    session = get_session_sync()
    for incident in incidents:
        logger.info("Processing incident", extra={"incident": incident.dict()})
        session.query(Incident).filter(
            Incident.source_provider_id == incident.source_provider_id,
            Incident.source_provider_type == incident.source_provider_type,
            Incident.source_unique_identifier == incident.source_unique_identifier,
        ).delete()
        create_incident_from_dto(tenant_id, incident)
        logger.info("Created incident", extra={"incident": incident.dict()})


async def async_process_incidents(*args, **kwargs):
    return process_incidents(*args, **kwargs)
