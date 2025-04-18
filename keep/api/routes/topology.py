import json
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic.v1 import BaseModel
from sqlmodel import Session

from keep.api.core.config import config
from keep.api.core.db import get_session, get_session_sync
from keep.api.core.tenant_configuration import TenantConfiguration
from keep.api.models.db.topology import (
    DeleteServicesRequest,
    TopologyApplicationDtoIn,
    TopologyApplicationDtoOut,
    TopologyService,
    TopologyServiceCreateRequestDTO,
    TopologyServiceDependencyCreateRequestDto,
    TopologyServiceDependencyDto,
    TopologyServiceDependencyUpdateRequestDto,
    TopologyServiceDtoIn,
    TopologyServiceDtoOut,
    TopologyServiceUpdateRequestDTO,
)
from keep.api.tasks.process_topology_task import process_topology
from keep.functions import cyaml
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.providers.base.base_provider import BaseTopologyProvider
from keep.providers.providers_factory import ProvidersFactory
from keep.topologies.topologies_service import (
    ApplicationNotFoundException,
    ApplicationParseException,
    DependencyNotFoundException,
    InvalidApplicationDataException,
    ServiceNotFoundException,
    ServiceNotManualException,
    TopologiesService,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# Add new model for topology processor settings
class TopologyProcessorSettings(BaseModel):
    enabled: bool
    lookBackWindow: int
    global_enabled: bool
    minimum_services: int


# GET topology processor settings
@router.get(
    "/settings",
    description="Get the topology processor settings",
    response_model=TopologyProcessorSettings,
)
def get_topology_processor_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:topology"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting topology processor settings", extra={"tenant_id": tenant_id})

    # Get default values from environment variables
    global_enabled = (
        config("KEEP_TOPOLOGY_PROCESSOR", default="false").lower() == "true"
    )
    default_look_back_window = config(
        "KEEP_TOPOLOGY_PROCESSOR_LOOK_BACK_WINDOW", cast=int, default=15
    )
    default_minimum_services = config(
        "KEEP_TOPOLOGY_PROCESSOR_MINIMUM_SERVICES", cast=int, default=2
    )

    tenant_config_client = TenantConfiguration()
    tenant_config = tenant_config_client.get_configuration(
        tenant_id, "topology_processor"
    )
    if tenant_config:
        enabled = tenant_config.get("enabled", global_enabled)
        look_back_window = tenant_config.get("lookBackWindow", default_look_back_window)
        minimum_services = tenant_config.get(
            "minimum_services", default_minimum_services
        )
        return TopologyProcessorSettings(
            enabled=enabled,
            lookBackWindow=look_back_window,
            global_enabled=global_enabled,
            minimum_services=minimum_services,
        )

    # For now, return the default values
    return TopologyProcessorSettings(
        enabled=False,  # if no tenant config, default to false
        lookBackWindow=default_look_back_window,
        global_enabled=global_enabled,
        minimum_services=default_minimum_services,
    )


# PUT topology processor settings
@router.put(
    "/settings",
    description="Update the topology processor settings",
    response_model=TopologyProcessorSettings,
)
def update_topology_processor_settings(
    settings: TopologyProcessorSettings,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:topology"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Updating topology processor settings",
        extra={
            "tenant_id": tenant_id,
            "settings": settings.dict(),
        },
    )

    # Validate settings
    if settings.lookBackWindow < 1:
        raise HTTPException(
            status_code=400, detail="Look back window must be a positive number"
        )

    if settings.minimum_services < 2:
        raise HTTPException(
            status_code=400, detail="Minimum services must be at least 2"
        )

    # Get global enabled status
    global_enabled = (
        config("KEEP_TOPOLOGY_PROCESSOR", default="false").lower() == "true"
    )

    tenant_config_client = TenantConfiguration()
    tenant_config = tenant_config_client.get_configuration(tenant_id)
    if not tenant_config:
        tenant_config = {}
    # Update the settings in the tenant configuration
    tenant_config["topology_processor"] = {
        "enabled": settings.enabled,
        "lookBackWindow": settings.lookBackWindow,
        "minimum_services": settings.minimum_services,
    }
    tenant_config_client.update_configuration(
        tenant_id=tenant_id,
        configuration=tenant_config,
    )

    # Return settings with current global_enabled status
    return TopologyProcessorSettings(
        enabled=settings.enabled,
        lookBackWindow=settings.lookBackWindow,
        global_enabled=global_enabled,
        minimum_services=settings.minimum_services,
    )


# GET all topology data
@router.get(
    "", description="Get all topology data", response_model=List[TopologyServiceDtoOut]
)
def get_topology_data(
    provider_ids: Optional[str] = None,
    services: Optional[str] = None,
    environment: Optional[str] = None,
    include_empty_deps: Optional[bool] = True,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:topology"])
    ),
    session: Session = Depends(get_session),
) -> List[TopologyServiceDtoOut]:
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting topology data", extra={tenant_id: tenant_id})
    topology_data = TopologiesService.get_all_topology_data(
        tenant_id, session, provider_ids, services, environment, include_empty_deps
    )
    return topology_data


@router.get(
    "/applications",
    description="Get all applications",
    response_model=List[TopologyApplicationDtoOut],
)
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
    except ApplicationParseException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/applications",
    description="Create a new application",
    response_model=TopologyApplicationDtoOut,
)
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
        return TopologiesService.create_application_by_tenant_id(
            tenant_id, application, session
        )
    except InvalidApplicationDataException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceNotFoundException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/applications/{application_id}",
    description="Update an application",
    response_model=TopologyApplicationDtoOut,
)
def update_application(
    application_id: UUID,
    application: TopologyApplicationDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:topology"])
    ),
    session: Session = Depends(get_session),
) -> TopologyApplicationDtoOut:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Updating application",
        extra={"tenant_id": tenant_id, "application_id": str(application_id)},
    )
    try:
        return TopologiesService.update_application_by_id(
            tenant_id, application_id, application, session
        )
    except ApplicationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidApplicationDataException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceNotFoundException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/applications/{application_id}", description="Delete an application")
def delete_application(
    application_id: UUID,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:topology"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Deleting application", extra={tenant_id: tenant_id})
    try:
        TopologiesService.delete_application_by_id(tenant_id, application_id, session)
        return JSONResponse(
            status_code=200, content={"message": "Application deleted successfully"}
        )
    except ApplicationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/pull",
    description="Pull topology data on demand from providers",
    response_model=List[TopologyServiceDtoOut],
)
def pull_topology_data(
    provider_ids: Optional[str] = None,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:topology"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Pulling topology data on demand",
        extra={"tenant_id": tenant_id, "provider_ids": provider_ids},
    )

    try:
        providers = ProvidersFactory.get_installed_providers(
            tenant_id=tenant_id, include_details=False
        )

        # Filter providers if provider_ids is specified
        if provider_ids:
            provider_id_list = provider_ids.split(",")
            providers = [p for p in providers if str(p.id) in provider_id_list]

        for provider in providers:
            extra = {
                "provider_type": provider.type,
                "provider_id": provider.id,
                "tenant_id": tenant_id,
            }

            try:
                provider_class = ProvidersFactory.get_installed_provider(
                    tenant_id=tenant_id,
                    provider_id=provider.id,
                    provider_type=provider.type,
                )

                if isinstance(provider_class, BaseTopologyProvider):
                    logger.info("Pulling topology data", extra=extra)
                    topology_data, applications_to_create = (
                        provider_class.pull_topology()
                    )
                    logger.info(
                        "Pulling topology data finished, processing",
                        extra={**extra, "topology_length": len(topology_data)},
                    )
                    process_topology(
                        tenant_id, topology_data, provider.id, provider.type
                    )
                    new_session = get_session_sync()
                    # now we want to create the applications
                    topology_data = TopologiesService.get_all_topology_data(
                        tenant_id, new_session, provider_ids=[provider.id]
                    )
                    for app in applications_to_create:
                        _app = TopologyApplicationDtoIn(
                            name=app,
                            services=[],
                        )
                        try:
                            # replace service name with service id
                            services = applications_to_create[app].get("services", [])
                            for service in services:
                                service_id = next(
                                    (
                                        s.id
                                        for s in topology_data
                                        if s.service == service
                                    ),
                                    None,
                                )
                                if not service_id:
                                    raise ServiceNotFoundException(service.service)
                                _app.services.append(
                                    TopologyServiceDtoIn(id=service_id)
                                )

                            # if the application already exists, update it
                            existing_apps = (
                                TopologiesService.get_applications_by_tenant_id(
                                    tenant_id, new_session
                                )
                            )
                            if any(a.name == app for a in existing_apps):
                                app_id = next(
                                    (a.id for a in existing_apps if a.name == app),
                                    None,
                                )
                                TopologiesService.update_application_by_id(
                                    tenant_id, app_id, _app, new_session
                                )
                            else:
                                TopologiesService.create_application_by_tenant_id(
                                    tenant_id, _app, session
                                )
                        except InvalidApplicationDataException as e:
                            logger.error(
                                f"Error creating application {app.name}: {str(e)}",
                                extra=extra,
                            )

                    logger.info("Finished processing topology data", extra=extra)
                else:
                    logger.debug(
                        f"Provider {provider.type} ({provider.id}) does not implement pulling topology data",
                        extra=extra,
                    )
            except NotImplementedError:
                logger.debug(
                    f"Provider {provider.type} ({provider.id}) does not implement pulling topology data",
                    extra=extra,
                )
            except Exception as e:
                logger.exception(
                    f"Error pulling topology from provider {provider.type} ({provider.id})",
                    extra={**extra, "error": str(e)},
                )

        # Return the updated topology data
        return TopologiesService.get_all_topology_data(
            tenant_id, session, provider_ids=provider_ids
        )

    except Exception as e:
        logger.exception(
            "Error during on-demand topology pull",
            extra={"tenant_id": tenant_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to pull topology data: {str(e)}"
        )


@router.post("/service", description="Creating a service manually")
def create_service(
    service: TopologyServiceCreateRequestDTO,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:topology"])
    ),
    session: Session = Depends(get_session),
) -> TopologyService:
    """
    Any services created by this endpoint will have manual set to True.
    """
    try:
        return TopologiesService.create_service(
            service=service, tenant_id=authenticated_entity.tenant_id, session=session
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create service: {str(e)}"
        )


@router.put("/service", description="Updating a service manually")
def update_service(
    service: TopologyServiceUpdateRequestDTO,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:topology"])
    ),
    session: Session = Depends(get_session),
) -> TopologyService:
    try:
        return TopologiesService.update_service(
            service=service, tenant_id=authenticated_entity.tenant_id, session=session
        )

    except ServiceNotManualException:
        raise HTTPException(
            status_code=404,
            detail="The service you're trying to updated was not created manually.",
        )
    except ServiceNotFoundException:
        raise HTTPException(status_code=404, detail="Service not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update service: {str(e)}"
        )


@router.delete("/services", description="Delete a list of services manually")
def delete_services(
    service_ids: DeleteServicesRequest,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:topology"])
    ),
    session: Session = Depends(get_session),
):
    try:
        TopologiesService.delete_services(
            service_ids=service_ids.service_ids,
            tenant_id=authenticated_entity.tenant_id,
            session=session,
        )
        return JSONResponse(
            status_code=200, content={"message": "Services deleted successfully"}
        )
    except ServiceNotManualException:
        raise HTTPException(
            status_code=404,
            detail="One or more service(s) you're trying to delete was not created manually.",
        )
    except ServiceNotFoundException:
        raise HTTPException(status_code=404, detail="Service not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete services: {str(e)}"
        )


@router.post("/dependency", description="Creating a new dependency manually")
def create_dependencies(
    dependency: TopologyServiceDependencyCreateRequestDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:topology"])
    ),
    session: Session = Depends(get_session),
) -> TopologyServiceDependencyDto:
    try:
        return TopologiesService.create_dependency(
            dependency=dependency,
            session=session,
            tenant_id=authenticated_entity.tenant_id,
        )
    except ServiceNotManualException:
        raise HTTPException(
            status_code=404,
            detail="You're tying to create a dependency between one or more pulled services.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create Dependency: {str(e)}"
        )


@router.put("/dependency", description="Updating a dependency manually")
def update_dependency(
    dependency: TopologyServiceDependencyUpdateRequestDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:topology"])
    ),
    session: Session = Depends(get_session),
) -> TopologyServiceDependencyDto:
    try:
        return TopologiesService.update_dependency(
            dependency=dependency,
            session=session,
            tenant_id=authenticated_entity.tenant_id,
        )
    except DependencyNotFoundException:
        raise HTTPException(status_code=404, detail="Dependency not found")
    except ServiceNotManualException:
        raise HTTPException(
            status_code=404,
            detail="You're tying to update a dependency between one or more pulled services.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update Dependency: {str(e)}"
        )


@router.delete(
    "/dependency/{dependency_id}", description="Deleting a dependency manually"
)
def delete_dependency(
    dependency_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:topology"])
    ),
    session: Session = Depends(get_session),
):
    try:
        TopologiesService.delete_dependency(
            dependency_id=dependency_id,
            session=session,
            tenant_id=authenticated_entity.tenant_id,
        )
        return JSONResponse(
            status_code=200, content={"message": "Dependency deleted successfully"}
        )
    except DependencyNotFoundException:
        raise HTTPException(status_code=404, detail="Dependency not found")
    except ServiceNotManualException:
        raise HTTPException(
            status_code=404,
            detail="You're tying to delete a dependency between two or more manual services.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete Dependency: {str(e)}"
        )


@router.get(
    "/export",
    description="Exporting the topology map as a YAML",
)
async def export_topology_yaml(
    services: Optional[str] = None,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:topology"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting topology data", extra={tenant_id: tenant_id})
    topology_data = TopologiesService.get_topology_services(
        tenant_id, session, None, services, None
    )
    full_data = {"applications": {}, "services": [], "dependencies": []}

    for data in topology_data:
        services_dict = data.model_dump()
        del services_dict["updated_at"]
        del services_dict["tenant_id"]
        services_dict["is_manual"] = (
            True if services_dict["is_manual"] is True else False
        )
        full_data["services"].append(services_dict)
        for application in data.applications:
            application_dict = application.model_dump()
            del application_dict["tenant_id"]
            application_dict["id"] = str(application_dict["id"])
            if application_dict["id"] in full_data["applications"]:
                full_data["applications"][application_dict["id"]]["services"].append(
                    data.id
                )
            else:
                application_dict["services"] = [data.id]
                full_data["applications"][application_dict["id"]] = application_dict
        for dependency in data.dependencies:
            dependency_dict = dependency.model_dump()
            del dependency_dict["updated_at"]
            full_data["dependencies"].append(dependency_dict)
    full_data["applications"] = list(full_data["applications"].values())
    export_yaml = cyaml.dump(full_data, width=99999)

    return Response(content=export_yaml, media_type="application/x-yaml")


@router.post(
    "/import",
    description="Import topology data from YAML or CSV file",
)
async def import_topology(
    file: UploadFile,
    format: str = Form("yaml"),  # Default format is yaml
    name: Optional[str] = Form(None),  # Optional topology name
    mapping: Optional[str] = Form(None),  # Field mapping for CSV
    correlation_settings: Optional[str] = Form(None),  # Correlation settings
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:topology"])
    ),
    session: Session = Depends(get_session),
):
    try:
        tenant_id = authenticated_entity.tenant_id
        file_content = await file.read()

        # Parse correlation settings if provided
        corr_settings = {}
        if correlation_settings:
            try:
                corr_settings = json.loads(correlation_settings)
                # Validate depth setting
                if "depth" in corr_settings and (
                    not isinstance(corr_settings["depth"], int)
                    or corr_settings["depth"] < 1
                ):
                    raise ValueError("Correlation depth must be a positive integer")
            except json.JSONDecodeError:
                logger.warning("Invalid correlation settings format, using defaults")
                corr_settings = {}

        # Get the tenant's minimum_services setting to include it in correlation settings
        tenant_config_client = TenantConfiguration()
        tenant_config = tenant_config_client.get_configuration(
            tenant_id, "topology_processor"
        )
        default_minimum_services = config(
            "KEEP_TOPOLOGY_PROCESSOR_MINIMUM_SERVICES", cast=int, default=2
        )
        minimum_services = default_minimum_services
        if tenant_config:
            minimum_services = tenant_config.get(
                "minimum_services", default_minimum_services
            )

        # Add minimum_services to correlation settings
        corr_settings["minimum_services"] = minimum_services

        if format.lower() == "yaml":
            # Process YAML file
            topology_data: dict = cyaml.safe_load(file_content)
            # For YAML imports, only pass the correlation_settings if it's a direct file import without applications
            if not topology_data.get("applications") and "depth" in corr_settings:
                TopologiesService.import_to_db(
                    topology_data, session, tenant_id, corr_settings
                )
            else:
                TopologiesService.import_to_db(topology_data, session, tenant_id, None)
            return JSONResponse(
                status_code=200, content={"message": "Topology imported successfully"}
            )

        elif format.lower() == "csv":
            # Process CSV file
            if not mapping:
                raise HTTPException(
                    status_code=400, detail="Field mapping is required for CSV import"
                )

            field_mapping = json.loads(mapping)
            TopologiesService.import_from_csv(
                csv_content=file_content,
                field_mapping=field_mapping,
                tenant_id=tenant_id,
                session=session,
                topology_name=name,
                correlation_settings=corr_settings,
            )
            return JSONResponse(
                status_code=200,
                content={"message": "Topology imported successfully from CSV"},
            )

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    except cyaml.YAMLError:
        logger.exception("Invalid YAML format")
        raise HTTPException(status_code=400, detail="Invalid YAML format")

    except json.JSONDecodeError:
        logger.exception("Invalid JSON mapping format")
        raise HTTPException(status_code=400, detail="Invalid JSON mapping format")

    except ValueError as e:
        logger.exception(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.exception(f"Failed to import topology: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to import topology: {str(e)}"
        )
