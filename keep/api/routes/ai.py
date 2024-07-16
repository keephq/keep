import logging

from fastapi import (
    APIRouter,
    Depends,
)

from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.api.core.db import get_incidents_count, get_alerts_count, get_first_alert_datetime

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/stats",
    description="Get stats for the AI Landing Page",
)
def get_stats(
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"]))
):
    tenant_id = authenticated_entity.tenant_id
    return {
        "alerts_count": get_alerts_count(tenant_id),
        "first_alert_datetime": get_first_alert_datetime(tenant_id),
        "incidents_count": get_incidents_count(tenant_id)
    }
