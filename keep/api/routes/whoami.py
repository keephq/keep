import logging

from fastapi import APIRouter, Depends

from keep.api.core.dependencies import verify_token_or_key

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "",
    description="Get tenant id",
)
def get_tenant_id(
    tenant_id: str = Depends(verify_token_or_key),
) -> dict:
    return {
        "tenant_id": tenant_id,
    }
