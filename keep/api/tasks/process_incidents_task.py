import logging

from keep.api.core.db import get_session_sync
from keep.api.core.dependencies import get_pusher_client
from keep.api.models.alert import IncidentDto
from keep.api.models.db.alert import Incident
from keep.api.routes.incidents import update_client_on_incident_change

logger = logging.getLogger(__name__)

TIMES_TO_RETRY_JOB = 5  # the number of times to retry the job in case of failure


def process_incidents(tenant_id: str, incidents: list[IncidentDto]):
    if not incidents:
        return

    session = get_session_sync()
    pusher_client = get_pusher_client()
    for incident in incidents:
        with session.begin():
            logger.info("Processing incident", extra={"incident": incident.dict()})
            session.query(Incident).filter(
                Incident.source_provider_id == incident.source_provider_id,
                Incident.source_provider_type == incident.source_provider_type,
                Incident.source_unique_identifier == incident.source_unique_identifier,
            ).delete()
            new_incident = Incident(
                **incident.dict(), tenant_id=tenant_id, is_confirmed=True
            )
            session.add(new_incident)
            session.commit()

            try:
                update_client_on_incident_change(pusher_client, tenant_id)
            except Exception:
                # We failed notifying the client but it's not that important atm
                pass

            logger.info("Created incident", extra={"incident": incident.dict()})


async def async_process_incidents(*args, **kwargs):
    return process_incidents(*args, **kwargs)
