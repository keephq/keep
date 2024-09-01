import logging

from fastapi import (
    APIRouter,
    Depends,
)

from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.api.core.db import get_incidents_count, get_alerts_count, get_first_alert_datetime
from keep.api.utils.import_ee import ALGORITHM_VERBOSE_NAME, is_ee_enabled_for_tenant


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/stats",
    description="Get stats for the AI Landing Page",
    include_in_schema=False,
)
def get_stats(
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"]))
):
    tenant_id = authenticated_entity.tenant_id
    return {
        "alerts_count": get_alerts_count(tenant_id),
        "first_alert_datetime": get_first_alert_datetime(tenant_id),
        "incidents_count": get_incidents_count(tenant_id),
        "is_mining_enabled": is_ee_enabled_for_tenant(tenant_id),
        "algorithm_verbose_name": str(ALGORITHM_VERBOSE_NAME)
    }
