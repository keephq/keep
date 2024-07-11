import logging

from fastapi import APIRouter, Depends

from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.api.core.db import get_last_alerts, create_incident, assign_alert_to_incident
from keep.api.core.incident_utils import mine_incidents

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "",
    description="Create incidents using historical alerts",
)
def create_incidents(
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier()),
    use_n_historical_alerts: int = 10000,
    incident_sliding_window_size: int = 6 * 24 * 60 * 60,
    statistic_sliding_window_size: int = 60 * 60,
    jaccard_threshold: float = 0.0,
    fingerprint_threshold: int = 1
) -> dict:
    tenant_id = authenticated_entity.tenant_id
    alerts = get_last_alerts(tenant_id, limit=use_n_historical_alerts)

    incidents = mine_incidents(alerts, incident_sliding_window_size,
                               statistic_sliding_window_size, jaccard_threshold, fingerprint_threshold)

    for incident in incidents:
        incident_id = create_incident(
            tenant_id, incident['incident_fingerprint']).id

        for alert in incident['alerts']:
            assign_alert_to_incident(alert.id, incident_id, tenant_id)

    return {"incidents": incidents}
