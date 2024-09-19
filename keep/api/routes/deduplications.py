import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException

from keep.api.alert_deduplicator.alert_deduplicator import AlertDeduplicator
from keep.api.models.alert import DeduplicationRuleRequestDto as DeduplicationRule
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
) -> dict[str, list[str]]:
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting deduplication fields")

    alert_deduplicator = AlertDeduplicator(tenant_id)
    fields = alert_deduplicator.get_deduplication_fields()

    logger.info("Got deduplication fields")
    return fields


@router.post(
    "",
    description="Create Deduplication Rule",
)
def create_deduplication_rule(
    rule: DeduplicationRule,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:deduplications"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Creating deduplication rule",
        extra={"tenant_id": tenant_id, "rule": rule.dict()},
    )
    alert_deduplicator = AlertDeduplicator(tenant_id)
    try:
        # This is a custom rule
        created_rule = alert_deduplicator.create_deduplication_rule(
            rule=rule, created_by=authenticated_entity.email
        )
        logger.info("Created deduplication rule")
        return created_rule
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception("Error creating deduplication rule")
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/{rule_id}",
    description="Update Deduplication Rule",
)
def update_deduplication_rule(
    rule_id: str,
    rule: DeduplicationRule,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:deduplications"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Updating deduplication rule", extra={"rule_id": rule_id})
    alert_deduplicator = AlertDeduplicator(tenant_id)
    try:
        updated_rule = alert_deduplicator.update_deduplication_rule(
            rule_id, rule, authenticated_entity.email
        )
        logger.info("Updated deduplication rule")
        return updated_rule
    except Exception as e:
        logger.exception("Error updating deduplication rule")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/{rule_id}",
    description="Delete Deduplication Rule",
)
def delete_deduplication_rule(
    rule_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:deduplications"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Deleting deduplication rule", extra={"rule_id": rule_id})
    alert_deduplicator = AlertDeduplicator(tenant_id)

    # verify rule id is uuid
    try:
        uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule id")

    try:
        success = alert_deduplicator.delete_deduplication_rule(rule_id)
        if success:
            logger.info("Deleted deduplication rule")
            return {"message": "Deduplication rule deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Deduplication rule not found")
    except HTTPException as e:
        logger.exception("Error deleting deduplication rule")
        # keep the same status code
        raise e
    except Exception as e:
        logger.exception("Error deleting deduplication rule")
        raise HTTPException(status_code=400, detail=str(e))
