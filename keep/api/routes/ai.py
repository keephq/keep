import logging
from typing import List
from typing import Any
from pydantic import BaseModel, Json

from fastapi import APIRouter, Body, Depends, Request

from keep.api.core.db import (
    get_alerts_count,
    get_first_alert_datetime,
    get_incidents_count,
    get_or_create_external_ai_settings,
    update_extrnal_ai_settings,
)
from keep.api.models.ai_external import ExternalAIConfigAndMetadataDto
from keep.api.utils.import_ee import ALGORITHM_VERBOSE_NAME
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
    return {
        "alerts_count": get_alerts_count(tenant_id),
        "first_alert_datetime": get_first_alert_datetime(tenant_id),
        "incidents_count": get_incidents_count(tenant_id),
        "algorithm_configs": get_or_create_external_ai_settings(tenant_id),
    }


@router.put(
    "/{algorithm_id}/settings",
    description="Update settings for an external AI",
    include_in_schema=False,
)
def update_settings(
    algorithm_id: str,
    body: ExternalAIConfigAndMetadataDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:alert"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    return update_extrnal_ai_settings(tenant_id, body)
