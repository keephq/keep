import logging

from fastapi import APIRouter, Depends

from keep.api.core.db import (
    get_alerts_count,
    get_first_alert_datetime,
    get_incidents_count,
)
from keep.api.core.tenant_configuration import TenantConfiguration
from keep.api.utils.import_ee import ALGORITHM_VERBOSE_NAME, is_ee_enabled_for_tenant
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/stats",
    description="Get stats for the AI Landing Page",
    include_in_schema=False,
)
def get_stats(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
):
    tenant_id = authenticated_entity.tenant_id

    tenant_configuration = TenantConfiguration()
    is_mining_enabled = is_ee_enabled_for_tenant(tenant_id, tenant_configuration)
    is_manual_mining_enabled = is_mining_enabled and tenant_configuration.get_configuration(tenant_id, "is_manual_mining_enabled")
    mining_configuration = tenant_configuration.get_configuration(tenant_id, "incident_mining_configuration") if is_mining_enabled else {}

    return {
        "alerts_count": get_alerts_count(tenant_id),
        "first_alert_datetime": get_first_alert_datetime(tenant_id),
        "incidents_count": get_incidents_count(tenant_id),
        "is_mining_enabled": is_mining_enabled,
        "is_manual_mining_enabled": is_manual_mining_enabled,
        "algorithm_verbose_name": str(ALGORITHM_VERBOSE_NAME),
        "mining_configuration": mining_configuration
    }
