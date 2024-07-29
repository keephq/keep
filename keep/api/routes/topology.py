import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from keep.api.core.db import (  # Assuming this function exists to fetch topology data
    get_all_topology_data,
)
from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.api.models.db.topology import TopologyServiceDtoOut

logger = logging.getLogger(__name__)
router = APIRouter()


# GET all topology data
@router.get(
    "", description="Get all topology data", response_model=List[TopologyServiceDtoOut]
)
def get_topology_data(
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["read:topology"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting topology data", extra={tenant_id: tenant_id})

    try:
        topology_data = get_all_topology_data(tenant_id)
        return topology_data
    except Exception:
        logger.exception("Failed to get topology data")
        raise HTTPException(
            status_code=400,
            detail="Unknown exception when getting topology data, please contact us",
        )
