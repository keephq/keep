import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from keep.api.core.db import get_session
from keep.api.core.dependencies import verify_token_or_key
from keep.api.models.db.preset import Preset, PresetDto, PresetOption

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "",
    description="Get all presets for tenant",
)
def get_presets(
    tenant_id: str = Depends(verify_token_or_key),
    session: Session = Depends(get_session),
) -> list[PresetDto]:
    logger.info("Getting all presets")
    statement = select(Preset).where(Preset.tenant_id == tenant_id)
    presets = session.exec(statement).all()
    logger.info("Got all presets")
    return [PresetDto(**preset.dict()) for preset in presets]


class CreateOrUpdatePresetDto(BaseModel):
    name: str | None
    options: list[PresetOption]


@router.post("", description="Create a preset for tenant")
def create_preset(
    body: CreateOrUpdatePresetDto,
    tenant_id: str = Depends(verify_token_or_key),
    session: Session = Depends(get_session),
) -> PresetDto:
    logger.info("Creating preset")
    if not body.options or not body.name:
        raise HTTPException(400, "Options and name are required")
    if body.name == "Feed" or body.name == "Deleted":
        raise HTTPException(400, "Cannot create preset with this name")
    options_dict = [option.dict() for option in body.options]
    preset = Preset(tenant_id=tenant_id, options=options_dict, name=body.name)
    session.add(preset)
    session.commit()
    session.refresh(preset)
    logger.info("Created preset")
    return PresetDto(**preset.dict())


@router.delete(
    "/{uuid}",
    description="Delete a preset for tenant",
)
def delete_preset(
    uuid: str,
    tenant_id: str = Depends(verify_token_or_key),
    session: Session = Depends(get_session),
):
    logger.info("Deleting preset", extra={"uuid": uuid})
    statement = (
        select(Preset).where(Preset.tenant_id == tenant_id).where(Preset.id == uuid)
    )
    preset = session.exec(statement).first()
    if not preset:
        raise HTTPException(404, "Preset not found")
    session.delete(preset)
    session.commit()
    logger.info("Deleted preset", extra={"uuid": uuid})
    return {}


@router.put(
    "/{uuid}",
    description="Update a preset for tenant",
)
def update_preset(
    uuid: str,
    body: CreateOrUpdatePresetDto,
    tenant_id: str = Depends(verify_token_or_key),
    session: Session = Depends(get_session),
) -> PresetDto:
    logger.info("Updating preset", extra={"uuid": uuid})
    statement = (
        select(Preset).where(Preset.tenant_id == tenant_id).where(Preset.id == uuid)
    )
    preset = session.exec(statement).first()
    if not preset:
        raise HTTPException(404, "Preset not found")
    if body.name:
        if body.name == "Feed" or body.name == "Deleted":
            raise HTTPException(400, "Cannot create preset with this name")
        if body.name != preset.name:
            preset.name = body.name
    options_dict = [option.dict() for option in body.options]
    if not options_dict:
        raise HTTPException(400, "Options cannot be empty")
    preset.options = options_dict
    session.commit()
    session.refresh(preset)
    logger.info("Updated preset", extra={"uuid": uuid})
    return PresetDto(**preset.dict())
