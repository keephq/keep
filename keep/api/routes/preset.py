import logging
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel
from sqlmodel import Session, select

from keep.api.consts import STATIC_PRESETS
from keep.api.core.db import get_preset_by_name as get_preset_by_name_db
from keep.api.core.db import get_presets as get_presets_db
from keep.api.core.db import get_session, update_preset_options
from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.api.models.alert import AlertDto
from keep.api.models.db.preset import Preset, PresetDto, PresetOption
from keep.api.tasks.process_event_task import process_event
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.providers_factory import ProvidersFactory
from keep.searchengine.searchengine import SearchEngine

router = APIRouter()
logger = logging.getLogger(__name__)


# SHAHAR: this function runs as background tasks as a seperate thread
#         DO NOT ADD async HERE as it will run in the main thread and block the whole server
def pull_alerts_from_providers(
    tenant_id: str,
    trace_id: str,
) -> list[AlertDto]:
    """
    Pulls alerts from providers and record the to the DB.

    "Get or create logics".
    """
    context_manager = ContextManager(
        tenant_id=tenant_id,
        workflow_id=None,
    )

    for provider in ProvidersFactory.get_installed_providers(tenant_id=tenant_id):
        provider_class = ProvidersFactory.get_provider(
            context_manager=context_manager,
            provider_id=provider.id,
            provider_type=provider.type,
            provider_config=provider.details,
        )
        logger.info(
            f"Pulling alerts from provider {provider.type} ({provider.id})",
            extra={
                "provider_type": provider.type,
                "provider_id": provider.id,
                "tenant_id": tenant_id,
            },
        )
        sorted_provider_alerts_by_fingerprint = (
            provider_class.get_alerts_by_fingerprint(tenant_id=tenant_id)
        )
        for fingerprint, alert in sorted_provider_alerts_by_fingerprint.items():
            process_event(
                {},
                tenant_id,
                provider.type,
                provider.id,
                fingerprint,
                None,
                trace_id,
                alert,
            )


@router.get(
    "",
    description="Get all presets for tenant",
)
def get_presets(
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier()),
) -> list[PresetDto]:
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting all presets")
    # both global and private presets
    presets = get_presets_db(tenant_id=tenant_id, email=authenticated_entity.email)
    presets_dto = [PresetDto(**preset.dict()) for preset in presets]
    # add static presets
    presets_dto.append(STATIC_PRESETS["feed"])
    presets_dto.append(STATIC_PRESETS["groups"])
    presets_dto.append(STATIC_PRESETS["dismissed"])
    logger.info("Got all presets")

    # get the number of alerts + noisy alerts for each preset
    search_engine = SearchEngine(tenant_id=tenant_id)
    # get the preset metatada
    presets_dto = search_engine.search_preset_alerts(presets=presets_dto)

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


@router.get(
    "/{preset_name}/alerts",
    description="Get a preset for tenant",
)
async def get_preset_alerts(
    request: Request,
    bg_tasks: BackgroundTasks,
    preset_name: str,
    response: Response,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier()),
) -> list[AlertDto]:

    # Gathering alerts may take a while and we don't care if it will finish before we return the response.
    # In the worst case, gathered alerts will be pulled in the next request.

    bg_tasks.add_task(
        pull_alerts_from_providers,
        authenticated_entity.tenant_id,
        request.state.trace_id,
    )

    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting preset alerts", extra={"preset_name": preset_name})
    # handle static presets
    if preset_name in STATIC_PRESETS:
        preset = STATIC_PRESETS[preset_name]
    else:
        preset = get_preset_by_name_db(tenant_id, preset_name)
    # if preset does not exist
    if not preset:
        raise HTTPException(404, "Preset not found")
    preset_dto = PresetDto(**preset.dict())
    search_engine = SearchEngine(tenant_id=tenant_id)
    preset_alerts = search_engine.search_alerts(preset_dto.query)
    logger.info("Got preset alerts", extra={"preset_name": preset_name})

    response.headers["X-search-type"] = str(search_engine.search_mode.value)
    return preset_alerts


class CreatePresetTab(BaseModel):
    name: str
    filter: str


@router.post(
    "/{preset_id}/tab",
    description="Create a tab for a preset",
)
def create_preset_tab(
    preset_id: str,
    body: CreatePresetTab,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier()),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Creating preset tab", extra={"preset_id": preset_id})
    statement = (
        select(Preset)
        .where(Preset.tenant_id == tenant_id)
        .where(Preset.id == preset_id)
    )
    preset = session.exec(statement).first()
    if not preset:
        raise HTTPException(404, "Preset not found")

    # get tabs
    tabs = []
    found = False
    for option in preset.options:
        if option.get("label", "").lower() == "tabs":
            tabs = option.get("value", [])
            found = True
            break

    # if its the first tab, create the tabs option
    if not found:
        preset.options.append({"label": "tabs", "value": []})

    tabs.append({"name": body.name, "id": str(uuid.uuid4()), "filter": body.filter})

    # update the tabs
    for option in preset.options:
        if option.get("label", "").lower() == "tabs":
            option["value"] = tabs
            break

    preset = update_preset_options(
        authenticated_entity.tenant_id, preset_id, preset.options
    )
    logger.info("Created preset tab", extra={"preset_id": preset_id})
    return PresetDto(**preset.dict())


@router.delete(
    "/{preset_id}/tab/{tab_id}",
    description="Delete a tab from a preset",
)
def delete_tab(
    preset_id: str,
    tab_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier()),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Deleting tab", extra={"tab_id": tab_id})
    statement = (
        select(Preset)
        .where(Preset.tenant_id == tenant_id)
        .where(Preset.id == preset_id)
    )
    preset = session.exec(statement).first()
    if not preset:
        raise HTTPException(404, "Preset not found")

    # get tabs
    tabs = []
    found = False
    for option in preset.options:
        if option.get("label", "").lower() == "tabs":
            tabs = option.get("value", [])
            found = True
            break

    # if tabs not found, return 404
    if not found:
        raise HTTPException(404, "Tabs not found")

    # remove the tab
    tabs = [tab for tab in tabs if tab.get("id") != tab_id]

    # update the tabs
    for option in preset.options:
        if option.get("label", "").lower() == "tabs":
            option["value"] = tabs
            break

    preset = update_preset_options(
        authenticated_entity.tenant_id, preset_id, preset.options
    )
    logger.info("Deleted tab", extra={"tab_id": tab_id})
    return PresetDto(**preset.dict())
