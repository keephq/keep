import logging

from fastapi import APIRouter, Depends

from keep.api.alert_deduplicator.alert_deduplicator import AlertDeduplicator
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()

logger = logging.getLogger(__name__)


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


@router.get(
    "/fields",
    description="Get Optional Fields For Deduplications",
)
def get_deduplication_fields(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:deduplications"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting deduplication fields")

    alert_deduplicator = AlertDeduplicator(tenant_id)
    fields = alert_deduplicator.get_deduplication_fields()

    logger.info("Got deduplication fields")
    return fields
