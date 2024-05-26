from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from keep.api.core.db import get_layouts as get_db_layouts
from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier


class GridLayoutCreateDTO(BaseModel):
    tenant_id: str
    layout_config: (
        Dict  # This should match the structure of your grid layout configuration
    )


class GridLayoutUpdateDTO(BaseModel):
    layout_config: Optional[Dict] = None  # Allow partial updates


class GridLayoutResponseDTO(BaseModel):
    id: str
    tenant_id: str
    layout_config: Dict
    created_at: datetime
    updated_at: datetime


router = APIRouter()


@router.get("", response_model=List[GridLayoutResponseDTO])
def read_layouts(authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier())):
    layouts = get_db_layouts(authenticated_entity.tenant_id)
    return layouts


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
