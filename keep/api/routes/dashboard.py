import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from keep.api.core.db import (
    create_dashboard as create_dashboard_db,
    get_provider_distribution,
    get_incidents_created_distribution,
    get_combined_workflow_execution_distribution,
    calc_incidents_mttr,
)
from keep.api.core.db import delete_dashboard as delete_dashboard_db
from keep.api.core.db import get_dashboards as get_dashboards_db
from keep.api.core.db import update_dashboard as update_dashboard_db
from keep.api.models.time_stamp import TimeStampFilter, _get_time_stamp_filter
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory


class DashboardCreateDTO(BaseModel):
    dashboard_name: str
    dashboard_config: Dict


class DashboardUpdateDTO(BaseModel):
    dashboard_config: Optional[Dict] = None  # Allow partial updates
    dashboard_name: Optional[str] = None


class DashboardResponseDTO(BaseModel):
    id: str
    dashboard_name: str
    dashboard_config: Dict
    created_at: datetime
    updated_at: datetime


router = APIRouter()
logger = logging.getLogger(__name__)


def provision_dashboards(tenant_id: str):
    try:
        dashboards_raw = json.loads(os.environ.get("KEEP_DASHBOARDS", "[]"))
    except Exception:
        logger.exception("Failed to load dashboards from environment variable")
        return
    if not dashboards_raw:
        logger.debug("No dashboards to provision")
        return
    logger.info(
        "Provisioning Dashboards", extra={"num_of_dashboards": len(dashboards_raw)}
    )
    dashboards_to_provision = [
        DashboardCreateDTO.parse_obj(dashboard) for dashboard in dashboards_raw
    ]
    for dashboard in dashboards_to_provision:
        logger.info(
            "Provisioning Dashboard",
            extra={"dashboard_name": dashboard.dashboard_name},
        )
        try:
            create_dashboard_db(
                tenant_id,
                dashboard.dashboard_name,
                "system",
                dashboard.dashboard_config,
            )
            logger.info(
                "Provisioned Dashboard",
                extra={"dashboard_name": dashboard.dashboard_name},
            )
        except Exception:
            logger.exception(
                "Failed to provision dashboard",
                extra={"dashboard_name": dashboard.dashboard_name},
            )
    logger.info(
        "Provisioned Dashboards", extra={"num_of_dashboards": len(dashboards_raw)}
    )


@router.get("", response_model=List[DashboardResponseDTO])
def read_dashboards(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:dashboards"])
    ),
):
    dashboards = get_dashboards_db(authenticated_entity.tenant_id)
    return dashboards


@router.post("", response_model=DashboardResponseDTO)
def create_dashboard(
    dashboard_dto: DashboardCreateDTO,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:dashboards"])
    ),
):
    email = authenticated_entity.email
    dashboard = create_dashboard_db(
        tenant_id=authenticated_entity.tenant_id,
        dashboard_name=dashboard_dto.dashboard_name,
        dashboard_config=dashboard_dto.dashboard_config,
        created_by=email,
    )
    return dashboard


@router.put("/{dashboard_id}", response_model=DashboardResponseDTO)
def update_dashboard(
    dashboard_id: str,
    dashboard_dto: DashboardUpdateDTO,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:dashboards"])
    ),
):
    # update the dashboard in the database
    dashboard = update_dashboard_db(
        tenant_id=authenticated_entity.tenant_id,
        dashboard_id=dashboard_id,
        dashboard_name=dashboard_dto.dashboard_name,
        dashboard_config=dashboard_dto.dashboard_config,
        updated_by=authenticated_entity.email,
    )
    return dashboard


@router.delete("/{dashboard_id}")
def delete_dashboard(
    dashboard_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:dashboards"])
    ),
):
    # delete the dashboard from the database
    dashboard = delete_dashboard_db(authenticated_entity.tenant_id, dashboard_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return {"ok": True}


@router.get("/metric-widgets")
def get_metric_widgets(
    time_stamp: TimeStampFilter = Depends(_get_time_stamp_filter),
    mttr: bool = True,
    apd: bool = True,
    ipd: bool = True,
    wpd: bool = True,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:dashboards"])
    ),
):
    data = {}
    tenant_id = authenticated_entity.tenant_id
    if not time_stamp.lower_timestamp or not time_stamp.upper_timestamp:
        time_stamp = TimeStampFilter(
            upper_timestamp=datetime.utcnow(),
            lower_timestamp=datetime.utcnow() - timedelta(hours=24),
        )
    if apd:
        data["apd"] = get_provider_distribution(
            tenant_id=tenant_id, aggregate_all=True, timestamp_filter=time_stamp
        )
    if ipd:
        data["ipd"] = get_incidents_created_distribution(
            tenant_id=tenant_id, timestamp_filter=time_stamp
        )
    if wpd:
        data["wpd"] = get_combined_workflow_execution_distribution(
            tenant_id=tenant_id, timestamp_filter=time_stamp
        )
    if mttr:
        data["mttr"] = calc_incidents_mttr(
            tenant_id=tenant_id, timestamp_filter=time_stamp
        )
    return data
