import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, or_


from keep.api.core.db import get_session
from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.api.models.db.preset import Preset, PresetDto, PresetOption

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "",
    description="Get all presets for tenant",
)
def get_presets(
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier()),
    session: Session = Depends(get_session),
) -> list[PresetDto]:
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting all presets")

    # only global presets
    statement = (
        select(Preset)
        .where(Preset.tenant_id == tenant_id)
        .where(
            or_(
                Preset.is_private == False,
                Preset.created_by == authenticated_entity.email,
            )
        )
    )

    presets = session.exec(statement).all()
    logger.info("Got all presets")
    return [PresetDto(**preset.dict()) for preset in presets]


class CreateOrUpdatePresetDto(BaseModel):
    name: str | None
    options: list[PresetOption]
    is_private: bool = False  # if true visible to all users of that tenant


@router.post("", description="Create a preset for tenant")
def create_preset(
    body: CreateOrUpdatePresetDto,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier()),
    session: Session = Depends(get_session),
) -> PresetDto:
    tenant_id = authenticated_entity.tenant_id
    if not body.options or not body.name:
        raise HTTPException(400, "Options and name are required")
    if body.name == "Feed" or body.name == "Deleted":
        raise HTTPException(400, "Cannot create preset with this name")
    options_dict = [option.dict() for option in body.options]

    created_by = authenticated_entity.email

    preset = Preset(
        tenant_id=tenant_id,
        options=options_dict,
        name=body.name,
        created_by=created_by,
        is_private=body.is_private,
    )

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
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier()),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
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
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier()),
    session: Session = Depends(get_session),
) -> PresetDto:
    tenant_id = authenticated_entity.tenant_id
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
    preset.is_private = body.is_private
    options_dict = [option.dict() for option in body.options]
    if not options_dict:
        raise HTTPException(400, "Options cannot be empty")
    preset.options = options_dict
    session.commit()
    session.refresh(preset)
    logger.info("Updated preset", extra={"uuid": uuid})
    return PresetDto(**preset.dict())
