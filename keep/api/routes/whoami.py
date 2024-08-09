import logging

from fastapi import APIRouter, Depends

from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "",
    description="Get tenant id",
)
def get_tenant_id(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
) -> dict:
    tenant_id = authenticated_entity.tenant_id
    return {
        "tenant_id": tenant_id,
    }
