import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, or_, select

from keep.api.core.db import get_alerts_with_filters, get_session
from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.api.models.alert import AlertStatus
from keep.api.models.db.preset import Preset, PresetDto, PresetOption
from keep.api.routes.alerts import convert_db_alerts_to_dto_alerts
from keep.rulesengine.rulesengine import RulesEngine

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

    # both global and private presets
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
    # for noisy presets, check if it needs to do noise now
    # TODO: improve performance e.g. using status as a filter
    # TODO: move this duplicate code to a module
    presets_dto = []
    for preset in presets:
        logger.info("Checking if preset is noisy")
        preset_dto = PresetDto(**preset.dict())
        if preset.is_noisy:
            # check if any firing alerts are present
            query = [
                option
                for option in preset.options
                if option.get("label", "").lower() == "cel"
            ]
            if not query:
                # should not happen
                logger.warning("No CEL query found in preset options")
                continue
            elif len(query) > 1:
                # should not happen
                logger.warning("Multiple CEL queries found in preset options")
                continue
            preset_query = query[0].get("value", "")
            # TODO: do this configurable
            timeframe_in_days = 3600 / 86400  # 1 hour in days
            # get the alerts
            alerts = get_alerts_with_filters(
                tenant_id=tenant_id, time_delta=timeframe_in_days
            )
            # convert the alerts to DTO
            alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
            # filter the alerts based on the search query
            filtered_alerts = RulesEngine.filter_alerts(alerts_dto, preset_query)
            firing_filtered_alerts = list(
                filter(
                    lambda alert: alert.status == AlertStatus.FIRING.value,
                    filtered_alerts,
                )
            )
            # if there are firing alerts, then do noise
            if firing_filtered_alerts:
                logger.info("Noisy preset is noisy")
                preset_dto.should_do_noise_now = True
            else:
                logger.info("Noisy preset is not noisy")
                preset_dto.should_do_noise_now = False
        presets_dto.append(preset_dto)
    return presets_dto


class CreateOrUpdatePresetDto(BaseModel):
    name: str | None
    options: list[PresetOption]
    is_private: bool = False  # if true visible to all users of that tenant
    is_noisy: bool = False  # if true, the preset will be noisy


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
        is_noisy=body.is_noisy,
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
    preset.is_noisy = body.is_noisy

    options_dict = [option.dict() for option in body.options]
    if not options_dict:
        raise HTTPException(400, "Options cannot be empty")
    preset.options = options_dict
    session.commit()
    session.refresh(preset)
    logger.info("Updated preset", extra={"uuid": uuid})
    return PresetDto(**preset.dict())
