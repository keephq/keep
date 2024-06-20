from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from keep.api.core.db import create_dashboard as create_dashboard_db
from keep.api.core.db import get_dashboards as get_dashboards_db
from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier


class DashboardCreateDTO(BaseModel):
    tenant_id: str
    dashboard_name: str
    dashboard_config: Dict


class DashboardUpdateDTO(BaseModel):
    dashboard_config: Optional[Dict] = None  # Allow partial updates


class DashboardResponseDTO(BaseModel):
    id: str
    tenant_id: str
    dashboard_config: Dict
    created_at: datetime
    updated_at: datetime


router = APIRouter()


@router.get("", response_model=List[DashboardResponseDTO])
def read_dashboards(
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier()),
):
    dashboards = get_dashboards_db(authenticated_entity.tenant_id)
    return dashboards


@router.post("", response_model=DashboardResponseDTO)
def create_dashboard(
    dashboard_dto: DashboardCreateDTO,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier()),
):
    email = authenticated_entity.email
    dashboard = create_dashboard_db(
        tenant_id=dashboard_dto.tenant_id,
        dashboard_name=dashboard_dto.dashboard_name,
        dashboard_config=dashboard_dto.dashboard_config,
        created_by=email,
    )
    return dashboard


"""
@router.post("/", response_model=GridLayoutResponseDTO)
def create_layout(
    layout_dto: GridLayoutCreateDTO,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier()),
):
    layout = GridLayout(
        tenant_id=layout_dto.tenant_id, layout_config=layout_dto.layout_config
    )
    layout = add_layout_db(tenant_id, layout)
    return layout


@router.get("/{layout_id}", response_model=GridLayoutResponseDTO)
def read_layout(
    layout_id: str, authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier())
):
    layout = get_db_layout(tenant_id, layout_id)
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")
    return layout


@router.put("/{layout_id}", response_model=GridLayoutResponseDTO)
def update_layout(
    layout_id: str,
    layout_dto: GridLayoutUpdateDTO,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier()),
):
    # update the layout in the database
    layout = update_db_layout(tenant_id, layout_id, layout_dto.layout_config)
    return layout


@router.delete("/{layout_id}")
def delete_layout(
    layout_id: str, authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier())
):
    # delete the layout from the database
    layout = delete_db_layout(tenant_id, layout_id)
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")
    return {"ok": True}
"""
