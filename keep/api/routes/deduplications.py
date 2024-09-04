import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from keep.api.alert_deduplicator.alert_deduplicator import AlertDeduplicator
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()

logger = logging.getLogger(__name__)


class DeduplicationDto(BaseModel):
    name: str
    description: str
    default: bool
    distribution: dict
    sources: list[str]
    last_updated: str
    last_updated_by: str
    created_at: str
    created_by: str
    enabled: bool


@router.get(
    "",
    description="Get Deduplications",
)
def get_deduplications(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:deduplications"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting deduplications")

    alert_deduplicator = AlertDeduplicator(tenant_id)
    deduplications = alert_deduplicator.get_deduplications()

    logger.info(deduplications)
    return deduplications
