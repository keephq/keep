import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from keep.api.core.db import get_session
from keep.api.core.dependencies import verify_token_or_key
from keep.api.models.db.preset import Preset, PresetDto

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


@router.post("/{name}", description="Create a preset for tenant")
def create_preset(
    name: str,
    options: list = [],
    tenant_id: str = Depends(verify_token_or_key),
    session: Session = Depends(get_session),
) -> PresetDto:
    # TODO: add validation for options
    logger.info("Creating preset")
    if not options:
        raise HTTPException(400, "Options cannot be empty")
    preset = Preset(tenant_id=tenant_id, options=options, name=name)
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
    name: str,
    options: list = [],
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
    preset.name = name
    preset.options = options
    session.commit()
    session.refresh(preset)
    logger.info("Updated preset", extra={"uuid": uuid})
    return PresetDto(**preset.dict())
