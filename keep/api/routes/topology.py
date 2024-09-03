import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from keep.api.core.db import (  # Assuming this function exists to fetch topology data
    get_all_topology_data,
)
from keep.api.models.db.topology import TopologyServiceDtoOut
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

logger = logging.getLogger(__name__)
router = APIRouter()


# GET all topology data
@router.get(
    "", description="Get all topology data", response_model=List[TopologyServiceDtoOut]
)
def get_topology_data(
    provider_id: Optional[str] = None,
    service_id: Optional[str] = None,
    environment: Optional[str] = None,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:topology"])
    ),
) -> List[TopologyServiceDtoOut]:
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting topology data", extra={tenant_id: tenant_id})

    # @tb: althought we expect all, we just take service_id for now.
    #   Checkout the `get_all_topology_data` function in db.py for more details
    # if (
    #     provider_id is not None or service_id is not None or environment is not None
    # ) and not (provider_id and service_id and environment):
    #     raise HTTPException(
    #         status_code=400,
    #         detail="If any of provider_id, service_id, or environment are provided, all must be provided.",
    #     )

    try:
        topology_data = get_all_topology_data(
            tenant_id, provider_id, service_id, environment
        )
        return topology_data
    except Exception:
        logger.exception("Failed to get topology data")
        raise HTTPException(
            status_code=400,
            detail="Unknown exception when getting topology data, please contact us",
        )
