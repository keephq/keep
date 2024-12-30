import logging
import os
import uuid
from datetime import datetime

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

from keep.api.consts import PROVIDER_PULL_INTERVAL_DAYS, STATIC_PRESETS
from keep.api.core.db import get_db_preset_by_name
from keep.api.core.db import get_presets as get_presets_db
from keep.api.core.db import (
    get_session,
    update_preset_options,
    update_provider_last_pull_time,
)
from keep.api.models.alert import AlertDto
from keep.api.models.db.preset import (
    Preset,
    PresetDto,
    PresetOption,
    PresetTagLink,
    Tag,
    TagDto,
)
from keep.api.models.time_stamp import TimeStampFilter, _get_time_stamp_filter
from keep.api.tasks.process_event_task import process_event
from keep.api.tasks.process_incident_task import process_incident
from keep.api.tasks.process_topology_task import process_topology
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.providers.base.base_provider import BaseIncidentProvider, BaseTopologyProvider
from keep.providers.providers_factory import ProvidersFactory
from keep.searchengine.searchengine import SearchEngine

router = APIRouter()
logger = logging.getLogger(__name__)


# SHAHAR: this function runs as background tasks as a seperate thread
#         DO NOT ADD async HERE as it will run in the main thread and block the whole server
def pull_data_from_providers(
    tenant_id: str,
    trace_id: str,
) -> list[AlertDto]:
    """
    Pulls alerts from providers and record the to the DB.

    "Get or create logics".
    """
    if os.environ.get("KEEP_PULL_DATA_ENABLED", "true") != "true":
        logger.debug("Pull data from providers is disabled")
        return

    providers = ProvidersFactory.get_installed_providers(
        tenant_id=tenant_id, include_details=False
    )

    logger.info(
        "Pulling data from providers",
        extra={
            "tenant_id": tenant_id,
            "trace_id": trace_id,
            "providers_len": len(providers),
        },
    )

    for provider in providers:
        extra = {
            "provider_type": provider.type,
            "provider_id": provider.id,
            "tenant_id": tenant_id,
            "trace_id": trace_id,
        }

        if not provider.pulling_enabled:
            logger.debug("Pulling is disabled for this provider", extra=extra)
            continue

        if provider.last_pull_time is not None:
            now = datetime.now()
            days_passed = (now - provider.last_pull_time).days
            if days_passed <= PROVIDER_PULL_INTERVAL_DAYS:
                logger.info(
                    "Skipping provider data pulling since not enough time has passed",
                    extra={
                        **extra,
                        "days_passed": days_passed,
                        "provider_last_pull_time": str(provider.last_pull_time),
                    },
                )
                continue

        try:
            logger.info(
                f"Pulling alerts from provider {provider.type} ({provider.id})",
                extra=extra,
            )
            # Even if we failed at processing some event, lets save the last pull time to not iterate this process over and over again.
            update_provider_last_pull_time(tenant_id=tenant_id, provider_id=provider.id)

            provider_class = ProvidersFactory.get_installed_provider(
                tenant_id=tenant_id,
                provider_id=provider.id,
                provider_type=provider.type,
            )
            sorted_provider_alerts_by_fingerprint = (
                provider_class.get_alerts_by_fingerprint(tenant_id=tenant_id)
            )
            logger.info(
                f"Pulling alerts from provider {provider.type} ({provider.id}) completed",
                extra=extra,
            )

            # TODO: this should be moved somewhere else (@tb: too much logic in this function, wil handle it another time.)
            if isinstance(provider_class, BaseIncidentProvider):
                try:
                    incidents = provider_class.get_incidents()
                    process_incident(
                        {},
                        tenant_id=tenant_id,
                        provider_id=provider.id,
                        provider_type=provider.type,
                        incidents=incidents,
                        trace_id=trace_id,
                    )
                except NotImplementedError:
                    logger.debug(
                        f"Provider {provider.type} ({provider.id}) does not implement pulling incidents",
                        extra=extra,
                    )
                except Exception:
                    logger.exception(
                        f"Unknown error pulling incidents from provider {provider.type} ({provider.id})",
                        extra={**extra, "trace_id": trace_id},
                    )
            else:
                logger.debug(
                    f"Provider {provider.type} ({provider.id}) does not implement pulling incidents",
                    extra=extra,
                )

            try:
                if isinstance(provider_class, BaseTopologyProvider):
                    logger.info("Pulling topology data", extra=extra)
                    topology_data, _ = provider_class.pull_topology()
                    logger.info(
                        "Pulling topology data finished, processing",
                        extra={**extra, "topology_length": len(topology_data)},
                    )
                    process_topology(
                        tenant_id, topology_data, provider.id, provider.type
                    )
                    logger.info("Finished processing topology data", extra=extra)
            except NotImplementedError:
                logger.debug(
                    f"Provider {provider.type} ({provider.id}) does not implement pulling topology data",
                    extra=extra,
                )
            except Exception:
                logger.exception(
                    f"Unknown error pulling topology from provider {provider.type} ({provider.id})",
                    extra={**extra},
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
                    notify_client=False,
                )
        except Exception as e:
            logger.exception(
                f"Unknown error pulling from provider {provider.type} ({provider.id})",
                extra={**extra, "exception": str(e)},
            )
    logger.info(
        "Pulling data from providers completed",
        extra={
            "tenant_id": tenant_id,
            "trace_id": trace_id,
            "providers_len": len(providers),
        },
    )


@router.get(
    "",
    description="Get all presets for tenant",
)
def get_presets(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:preset"])
    ),
    session: Session = Depends(get_session),
    time_stamp: TimeStampFilter = Depends(_get_time_stamp_filter),
) -> list[PresetDto]:
    tenant_id = authenticated_entity.tenant_id
    logger.info(f"Getting all presets {time_stamp}")

    # get all preset ids that the user has access to
    identity_manager = IdentityManagerFactory.get_identity_manager(
        authenticated_entity.tenant_id
    )
    # Note: if no limitations (allowed_preset_ids is []), then all presets are allowed
    allowed_preset_ids = identity_manager.get_user_permission_on_resource_type(
        resource_type="preset",
        authenticated_entity=authenticated_entity,
    )
    # both global and private presets
    presets = get_presets_db(
        tenant_id=tenant_id,
        email=authenticated_entity.email,
        preset_ids=allowed_preset_ids,
    )
    presets_dto = [PresetDto(**preset.to_dict()) for preset in presets]
    # add static presets (unless allowed_preset_ids is set)
    if not allowed_preset_ids:
        presets_dto.append(STATIC_PRESETS["feed"])
    logger.info("Got all presets")

    # get the number of alerts + noisy alerts for each preset
    search_engine = SearchEngine(tenant_id=tenant_id)
    # get the preset metatada
    presets_dto = search_engine.search_preset_alerts(
        presets=presets_dto, time_stamp=time_stamp
    )

    return presets_dto


class CreateOrUpdatePresetDto(BaseModel):
    name: str | None
    options: list[PresetOption]
    is_private: bool = False  # if true visible to all users of that tenant
    is_noisy: bool = False  # if true, the preset will be noisy
    tags: list[TagDto] = []  # tags to assign to the preset


@router.post("", description="Create a preset for tenant")
def create_preset(
    body: CreateOrUpdatePresetDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:presets"])
    ),
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

    # Handle tags
    tags = []
    for tag in body.tags:
        # New tag, create it
        if not tag.id:
            # check if tag with the same name already exists
            # (can happen due to some sync problems)
            existing_tag = session.query(Tag).filter(Tag.name == tag.name).first()
            if existing_tag:
                tags.append(existing_tag)
                continue
            new_tag = Tag(name=tag.name, tenant_id=tenant_id)
            session.add(new_tag)
            session.commit()
            session.refresh(new_tag)
            tags.append(new_tag)
        else:
            existing_tag = session.get(Tag, tag.id)
            if existing_tag is None:
                raise HTTPException(400, f"Tag with id {tag.id} does not exist")
            tags.append(existing_tag)

    # Add preset and commit to generate preset ID
    session.add(preset)
    session.commit()
    session.refresh(preset)

    # Explicitly create PresetTagLink entries
    for tag in tags:
        preset_tag_link = PresetTagLink(
            tenant_id=tenant_id, preset_id=preset.id, tag_id=tag.id
        )
        session.add(preset_tag_link)

    session.commit()
    session.refresh(preset)
    logger.info("Created preset")
    return PresetDto(**preset.to_dict())


@router.delete(
    "/{preset_id}",
    description="Delete a preset for tenant",
)
def delete_preset(
    preset_id: uuid.UUID,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["delete:presets"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Deleting preset", extra={"uuid": preset_id})
    # Delete links
    session.query(PresetTagLink).filter(PresetTagLink.preset_id == preset_id).delete()

    statement = (
        select(Preset)
        .where(Preset.tenant_id == tenant_id)
        .where(Preset.id == preset_id)
    )
    preset = session.exec(statement).first()
    if not preset:
        raise HTTPException(404, "Preset not found")
    session.delete(preset)
    session.commit()
    logger.info("Deleted preset", extra={"uuid": preset_id})
    return {}


@router.put(
    "/{preset_id}",
    description="Update a preset for tenant",
)
def update_preset(
    preset_id: uuid.UUID,
    body: CreateOrUpdatePresetDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:presets"])
    ),
    session: Session = Depends(get_session),
) -> PresetDto:
    tenant_id = authenticated_entity.tenant_id
    logger.info("Updating preset", extra={"uuid": preset_id})
    statement = (
        select(Preset)
        .where(Preset.tenant_id == tenant_id)
        .where(Preset.id == preset_id)
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

    # Handle tags
    tags = []
    for tag in body.tags:
        # New tag, create it
        if not tag.id:
            # check if tag with the same name already exists
            # (can happen due to some sync problems)
            existing_tag = session.query(Tag).filter(Tag.name == tag.name).first()
            if existing_tag:
                tags.append(existing_tag)
                continue
            new_tag = Tag(name=tag.name, tenant_id=tenant_id)
            session.add(new_tag)
            session.commit()
            session.refresh(new_tag)
            tags.append(new_tag)
        else:
            existing_tag = session.get(Tag, tag.id)
            if existing_tag is None:
                raise HTTPException(400, f"Tag with id {tag.id} does not exist")
            tags.append(existing_tag)

    # Clear existing tag links
    session.query(PresetTagLink).filter(PresetTagLink.preset_id == preset.id).delete()

    # Explicitly create PresetTagLink entries
    for tag in tags:
        preset_tag_link = PresetTagLink(
            tenant_id=tenant_id, preset_id=preset.id, tag_id=tag.id
        )
        session.add(preset_tag_link)

    session.commit()
    session.refresh(preset)
    logger.info("Updated preset", extra={"uuid": preset_id})
    return PresetDto(**preset.to_dict())


@router.get(
    "/{preset_name}/alerts",
    description="Get the alerts of a preset",
)
def get_preset_alerts(
    request: Request,
    bg_tasks: BackgroundTasks,
    preset_name: str,
    response: Response,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:presets"])
    ),
) -> list:

    # Gathering alerts may take a while and we don't care if it will finish before we return the response.
    # In the worst case, gathered alerts will be pulled in the next request.

    bg_tasks.add_task(
        pull_data_from_providers,
        authenticated_entity.tenant_id,
        request.state.trace_id,
    )

    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Getting preset alerts",
        extra={"preset_name": preset_name, "tenant_id": tenant_id},
    )
    # handle static presets
    if preset_name in STATIC_PRESETS:
        preset = STATIC_PRESETS[preset_name]
    else:
        preset = get_db_preset_by_name(tenant_id, preset_name)
    # if preset does not exist
    if not preset:
        raise HTTPException(404, "Preset not found")
    if isinstance(preset, Preset):
        preset_dto = PresetDto(**preset.to_dict())
    else:
        preset_dto = PresetDto(**preset.dict())

    # get all preset ids that the user has access to
    identity_manager = IdentityManagerFactory.get_identity_manager(
        authenticated_entity.tenant_id
    )
    # Note: if no limitations (allowed_preset_ids is []), then all presets are allowed
    allowed_preset_ids = identity_manager.get_user_permission_on_resource_type(
        resource_type="preset",
        authenticated_entity=authenticated_entity,
    )
    if allowed_preset_ids and str(preset_dto.id) not in allowed_preset_ids:
        raise HTTPException(403, "Not authorized to access this preset")

    search_engine = SearchEngine(tenant_id=tenant_id)
    preset_alerts = search_engine.search_alerts(preset_dto.query)
    logger.info("Got preset alerts", extra={"preset_name": preset_name})

    response.headers["X-Search-Type"] = str(search_engine.search_mode.value)
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
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:presets"])
    ),
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
    return PresetDto(**preset.to_dict())


@router.delete(
    "/{preset_id}/tab/{tab_id}",
    description="Delete a tab from a preset",
)
def delete_tab(
    preset_id: str,
    tab_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["delete:presets"])
    ),
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
    return PresetDto(**preset.to_dict())
