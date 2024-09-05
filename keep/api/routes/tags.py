from fastapi import APIRouter, Depends

from keep.api.core.db import get_tags as get_tags_db
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()


@router.get("", description="get tags")
def get_tags(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:presets"])
    ),
) -> list[dict]:
    tags = get_tags_db(authenticated_entity.tenant_id)
    return tags
