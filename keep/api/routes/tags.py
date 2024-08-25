from fastapi import APIRouter, Depends

from keep.api.core.db import get_tags as get_tags_db
from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier

router = APIRouter()


@router.get("", description="get tags")
def get_tags(
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["read:settings"])
    ),
) -> list[dict]:
    tags = get_tags_db(authenticated_entity.tenant_id)
    return tags
