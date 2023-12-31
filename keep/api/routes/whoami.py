import logging

from fastapi import APIRouter, Depends

from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "",
    description="Get tenant id",
)
def get_tenant_id(
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier()),
) -> dict:
    tenant_id = authenticated_entity.tenant_id
    return {
        "tenant_id": tenant_id,
    }
