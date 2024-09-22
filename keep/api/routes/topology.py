import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session

from keep.api.core.db import get_session
from keep.api.models.db.topology import TopologyApplicationDtoIn, TopologyApplicationDtoOut, TopologyServiceDtoOut
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.topologies.topologies_service import TopologiesService

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
    includeEmptyDeps: Optional[bool] = False,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:topology"])
    ),
    session: Session = Depends(get_session),
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
        topology_data = TopologiesService.get_all_topology_data(
            tenant_id, session, provider_id, service_id, environment, includeEmptyDeps
        )
        return topology_data
    except Exception:
        logger.exception("Failed to get topology data")
        raise HTTPException(
            status_code=400,
            detail="Unknown exception when getting topology data, please contact us",
        )


@router.get("/applications", description="Get all applications", response_model=List[TopologyApplicationDtoOut])
def get_applications(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:topology"])
    ),
    session: Session = Depends(get_session),
) -> List[TopologyApplicationDtoOut]:
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting applications", extra={"tenant_id": tenant_id})
    try:
        return TopologiesService.get_applications_by_tenant_id(tenant_id, session)
    except Exception as e:
        logger.exception(f"Failed to get applications: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Unknown exception when getting applications, please contact us",
        )
    
@router.post("/applications", description="Create a new application", response_model=TopologyApplicationDtoOut)
def create_application(
    application: TopologyApplicationDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:topology"])
    ),
    session: Session = Depends(get_session),
) -> TopologyApplicationDtoOut:
    tenant_id = authenticated_entity.tenant_id
    logger.info("Creating application", extra={tenant_id: tenant_id})
    try:
        return TopologiesService.create_application_by_tenant_id(tenant_id, application, session)
    except Exception:
        logger.exception("Failed to create application")
        raise HTTPException(
            status_code=400,
            detail="Unknown exception when creating application, please contact us",
        )
    
@router.put("/applications/{application_id}", description="Update an application", response_model=TopologyApplicationDtoOut)
def update_application(
    application_id: str,
    application: TopologyApplicationDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:topology"])
    ),
    session: Session = Depends(get_session),
) -> TopologyApplicationDtoOut:
    tenant_id = authenticated_entity.tenant_id
    logger.info("Updating application", extra={tenant_id: tenant_id})
    try:
        return TopologiesService.update_application_by_id(tenant_id, application_id, application, session)
    except Exception:
        logger.exception("Failed to update application")
        raise HTTPException(
            status_code=400,
            detail="Unknown exception when updating application, please contact us",
        )

@router.delete("/applications/{application_id}", description="Delete an application")
def delete_application(
    application_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:topology"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Deleting application", extra={tenant_id: tenant_id})
    try:
        TopologiesService.delete_application_by_id(tenant_id, application_id, session)
        return JSONResponse(status_code=200, content={"message": "Application deleted successfully"})
    except Exception:
        logger.exception("Failed to delete application")
        raise HTTPException(
            status_code=400,
            detail="Unknown exception when deleting application, please contact us",
        )
