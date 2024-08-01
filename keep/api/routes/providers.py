import datetime
import json
import logging
import time
import uuid
from typing import Callable, Optional

import sqlalchemy
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from starlette.datastructures import UploadFile

from keep.api.core.config import config
from keep.api.core.db import get_provider_distribution, get_session, count_alerts
from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.api.models.db.provider import Provider
from keep.api.models.provider import ProviderAlertsCountResponseDTO
from keep.api.models.webhook import ProviderWebhookSettings
from keep.api.utils.tenant_utils import get_or_create_api_key
from keep.contextmanager.contextmanager import ContextManager
from keep.event_subscriber.event_subscriber import EventSubscriber
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.base.provider_exceptions import (
    GetAlertException,
    ProviderMethodException,
)
from keep.providers.providers_factory import ProvidersFactory
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)

PROVIDER_DISTRIBUTION_ENABLED = config(
    "PROVIDER_DISTRIBUTION_ENABLED", cast=bool, default=True
)


def _is_localhost():
    # TODO - there are more "advanced" cases that we don't catch here
    #        e.g. IP's that are not public but not localhost
    #        the more robust way is to try access KEEP_API_URL from another tool (such as wtfismy.com but the opposite)
    #
    #        this is a temporary solution until we have a better one
    api_url = config("KEEP_API_URL")
    if "localhost" in api_url:
        return True

    if "127.0.0" in api_url:
        return True

    # default on localhost if no USE_NGROK
    if "0.0.0.0" in api_url:
        return True

    return False


@router.get(
    "",
)
def get_providers(
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["read:providers"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting installed providers", extra={"tenant_id": tenant_id})
    providers = ProvidersFactory.get_all_providers()
    installed_providers = ProvidersFactory.get_installed_providers(
        tenant_id, providers, include_details=True
    )

    linked_providers = []

    if PROVIDER_DISTRIBUTION_ENABLED:
        linked_providers = ProvidersFactory.get_linked_providers(tenant_id)
        providers_distribution = get_provider_distribution(tenant_id)

        for provider in linked_providers + installed_providers:
            provider.alertsDistribution = providers_distribution.get(
                f"{provider.id}_{provider.type}", {}
            ).get("alert_last_24_hours", [])
            last_alert_received = providers_distribution.get(
                f"{provider.id}_{provider.type}", {}
            ).get("last_alert_received", None)
            if last_alert_received and not provider.last_alert_received:
                provider.last_alert_received = last_alert_received.replace(
                    tzinfo=datetime.timezone.utc
                ).isoformat()

    is_localhost = _is_localhost()

    try:
        return {
            "providers": providers,
            "installed_providers": installed_providers,
            "linked_providers": linked_providers,
            "is_localhost": is_localhost,
        }
    except Exception:
        logger.exception("Failed to get providers")
        return {
            "providers": providers,
            "installed_providers": [],
            "linked_providers": [],
            "is_localhost": is_localhost,
        }


@router.get("/export", description="export all installed providers")
def get_installed_providers(
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["read:providers"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting installed providers", extra={"tenant_id": tenant_id})
    providers = ProvidersFactory.get_all_providers()
    installed_providers = ProvidersFactory.get_installed_providers(
        tenant_id, providers, include_details=True
    )

    is_localhost = _is_localhost()

    try:
        return {
            "installed_providers": installed_providers,
            "is_localhost": is_localhost,
        }
    except Exception as e:
        logger.info(f"execption in {e}")
        logger.exception("Failed to get providers")
        return {"installed_providers": [], "is_localhost": is_localhost}


@router.get(
    "/{provider_type}/{provider_id}/configured-alerts",
    description="Get alerts configuration from a provider",
)
def get_alerts_configuration(
    provider_type: str,
    provider_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["read:providers"])
    ),
) -> list:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Getting provider alerts",
        extra={
            "tenant_id": tenant_id,
            "provider_type": provider_type,
            "provider_id": provider_id,
        },
    )
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    provider_config = secret_manager.read_secret(
        f"{tenant_id}_{provider_type}_{provider_id}", is_json=True
    )
    provider = ProvidersFactory.get_provider(
        context_manager, provider_id, provider_type, provider_config
    )
    return provider.get_alerts_configuration()


@router.get(
    "/{provider_type}/{provider_id}/logs",
    description="Get logs from a provider",
)
def get_logs(
    provider_type: str,
    provider_id: str,
    limit: int = 5,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["read:providers"])
    ),
) -> list:
    try:
        tenant_id = authenticated_entity.tenant_id
        logger.info(
            "Getting provider logs",
            extra={
                "tenant_id": tenant_id,
                "provider_type": provider_type,
                "provider_id": provider_id,
            },
        )
        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        provider_config = secret_manager.read_secret(
            f"{tenant_id}_{provider_type}_{provider_id}", is_json=True
        )
        provider = ProvidersFactory.get_provider(
            context_manager, provider_id, provider_type, provider_config
        )
        return provider.get_logs(limit=limit)
    except ModuleNotFoundError:
        raise HTTPException(404, detail=f"Provider {provider_type} not found")
    except Exception:
        logger.exception(
            "Failed to get provider logs",
            extra={
                "tenant_id": tenant_id,
                "provider_type": provider_type,
                "provider_id": provider_id,
            },
        )
        return []


@router.get(
    "/{provider_type}/schema",
    description="Get the provider's API schema used to push alerts configuration",
)
def get_alerts_schema(
    provider_type: str,
) -> dict:
    try:
        logger.info(
            "Getting provider alerts schema", extra={"provider_type": provider_type}
        )
        provider = ProvidersFactory.get_provider_class(provider_type)
        return provider.get_alert_schema()
    except ModuleNotFoundError:
        raise HTTPException(404, detail=f"Provider {provider_type} not found")


@router.get(
    "/{provider_type}/{provider_id}/alerts/count",
    description="Get number of alerts a specific provider has received (in a specific time time period or ever)",
)
def get_alert_count(
    provider_type: str,
    provider_id: str,
    ever: bool,
    start_time: Optional[datetime.datetime] = None,
    end_time: Optional[datetime.datetime] = None,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
):
    tenant_id = authenticated_entity.tenant_id
    if ever is False and (start_time is None or end_time is None):
        return HTTPException(
            status_code=400, detail="Missing start_time and/or end_time"
        )
    return ProviderAlertsCountResponseDTO(
        count=count_alerts(
            provider_type=provider_type,
            provider_id=provider_id,
            ever=ever,
            start_time=start_time,
            end_time=end_time,
            tenant_id=tenant_id,
        ),
    )


@router.post(
    "/{provider_type}/{provider_id}/alerts",
    description="Push new alerts to the provider",
)
def add_alert(
    provider_type: str,
    provider_id: str,
    alert: dict,
    alert_id: Optional[str] = None,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["write:alert"])),
) -> JSONResponse:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Adding alert to provider",
        extra={
            "tenant_id": tenant_id,
            "provider_type": provider_type,
            "provider_id": provider_id,
        },
    )
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    # TODO: secrets convention from config?
    provider_config = secret_manager.read_secret(
        f"{tenant_id}_{provider_type}_{provider_id}", is_json=True
    )
    provider = ProvidersFactory.get_provider(
        context_manager, provider_id, provider_type, provider_config
    )
    try:
        provider.deploy_alert(alert, alert_id)
        return JSONResponse(status_code=200, content={"message": "deployed"})
    except Exception as e:
        return JSONResponse(status_code=500, content=e.args[0])


@router.post(
    "/test",
    description="Test a provider's alert retrieval",
)
def test_provider(
    provider_info: dict = Body(...),
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["read:providers"])
    ),
) -> JSONResponse:
    # Extract parameters from the provider_info dictionary
    # For now, we support only 1:1 provider_type:provider_id
    # In the future, we might want to support multiple providers of the same type
    tenant_id = authenticated_entity.tenant_id
    provider_id = provider_info.pop("provider_id")
    provider_type = provider_info.pop("provider_type", None) or provider_id
    logger.info(
        "Testing provider",
        extra={
            "provider_id": provider_id,
            "provider_type": provider_type,
            "tenant_id": tenant_id,
        },
    )
    provider_config = {
        "authentication": provider_info,
    }
    # TODO: valdiations:
    # 1. provider_type and provider id is valid
    # 2. the provider config is valid
    context_manager = ContextManager(
        tenant_id=tenant_id, workflow_id=""  # this is not in a workflow scope
    )
    provider = ProvidersFactory.get_provider(
        context_manager, provider_id, provider_type, provider_config
    )
    try:
        alerts = provider.get_alerts_configuration()
        return JSONResponse(status_code=200, content={"alerts": alerts})
    except GetAlertException as e:
        return JSONResponse(status_code=e.status_code, content=e.message)
    except Exception as e:
        return JSONResponse(status_code=400, content=str(e))


@router.delete("/{provider_type}/{provider_id}")
def delete_provider(
    provider_type: str,
    provider_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["delete:providers"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Deleting provider",
        extra={
            "provider_id": provider_id,
            "tenant_id": tenant_id,
        },
    )
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    try:
        provider = session.exec(
            select(Provider).where(
                (Provider.tenant_id == tenant_id) & (Provider.id == provider_id)
            )
        ).one()
        try:
            secret_manager.delete_secret(provider.configuration_key)
        # in case the secret does not deleted, just log it but still
        # delete the provider so
        except Exception:
            logger.exception("Failed to delete the provider secret")
            pass
        # delete the provider anyway
        session.delete(provider)
        session.commit()
    except sqlalchemy.orm.exc.NoResultFound:
        raise HTTPException(404, detail="Provider not found")
    except Exception:
        # TODO: handle it better
        logger.exception("Failed to delete the provider secret")
        pass

    if provider.consumer:
        # Unregister the provider as a consumer
        try:
            event_subscriber = EventSubscriber.get_instance()
            event_subscriber.remove_consumer(provider)
        except Exception:
            logger.exception("Failed to unregister provider as a consumer")
            # return 200 as the next time Keep will start, it will try to unregister again
    logger.info("Deleted provider", extra={"provider_id": provider_id})
    return JSONResponse(status_code=200, content={"message": "deleted"})


def validate_scopes(
    provider: BaseProvider, validate_mandatory=True
) -> dict[str, bool | str]:
    logger.info("Validating provider scopes")
    try:
        validated_scopes = provider.validate_scopes()
    except Exception as e:
        logger.exception("Failed to validate provider scopes")
        raise HTTPException(
            status_code=412,
            detail=str(e),
        )
    if validate_mandatory:
        mandatory_scopes_validated = True
        if provider.PROVIDER_SCOPES and validated_scopes:
            # All of the mandatory scopes must be validated
            for scope in provider.PROVIDER_SCOPES:
                if scope.mandatory and (
                    scope.name not in validated_scopes
                    or validated_scopes[scope.name] is not True
                ):
                    mandatory_scopes_validated = False
                    break
        # Otherwise we fail the installation
        if not mandatory_scopes_validated:
            logger.warning(
                "Failed to validate mandatory provider scopes",
                extra={"validated_scopes": validated_scopes},
            )
            raise HTTPException(
                status_code=412,
                detail=validated_scopes,
            )
    logger.info(
        "Validated provider scopes", extra={"validated_scopes": validated_scopes}
    )
    return validated_scopes


@router.post(
    "/{provider_id}/scopes",
    description="Validate provider scopes",
    status_code=200,
    response_model=dict[str, bool | str],
)
def validate_provider_scopes(
    provider_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:providers"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Validating provider scopes", extra={"provider_id": provider_id})
    provider = session.exec(
        select(Provider).where(
            (Provider.tenant_id == tenant_id) & (Provider.id == provider_id)
        )
    ).one()

    if not provider:
        raise HTTPException(404, detail="Provider not found")

    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    provider_config = secret_manager.read_secret(
        provider.configuration_key, is_json=True
    )
    provider_instance = ProvidersFactory.get_provider(
        context_manager, provider_id, provider.type, provider_config
    )
    validated_scopes = provider_instance.validate_scopes()
    if validated_scopes != provider.validatedScopes:
        provider.validatedScopes = validated_scopes
        session.commit()
    logger.info(
        "Validated provider scopes",
        extra={"provider_id": provider_id, "validated_scopes": validate_scopes},
    )
    return validated_scopes


@router.put("/{provider_id}", description="Update provider", status_code=200)
async def update_provider(
    provider_id: str,
    request: Request,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["update:providers"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    updated_by = authenticated_entity.email
    logger.info(
        "Updating provider",
        extra={
            "provider_id": provider_id,
        },
    )
    try:
        provider_info = await request.json()
    except Exception:
        # If error occurs (likely not JSON), try to get as form data
        form_data = await request.form()
        provider_info = dict(form_data)

    if not provider_info:
        raise HTTPException(status_code=400, detail="No valid data provided")

    provider = session.exec(
        select(Provider).where(
            (Provider.tenant_id == tenant_id) & (Provider.id == provider_id)
        )
    ).one()

    if not provider:
        raise HTTPException(404, detail="Provider not found")

    provider_config = {
        "authentication": provider_info,
        "name": provider.name,
    }

    # we support files as well
    for key, value in provider_config.get("authentication", {}).items():
        if isinstance(value, UploadFile):
            provider_config["authentication"][key] = await value.read()
            provider_config["authentication"][key] = provider_config["authentication"][
                key
            ].decode()

    context_manager = ContextManager(tenant_id=tenant_id)
    try:
        provider_instance = ProvidersFactory.get_provider(
            context_manager, provider_id, provider.type, provider_config
        )
    except (ProviderException, ProviderConfigException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    validated_scopes = validate_scopes(provider_instance)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    secret_manager.write_secret(
        secret_name=provider.configuration_key, secret_value=json.dumps(provider_config)
    )
    provider.installed_by = updated_by
    provider.validatedScopes = validated_scopes
    session.commit()
    logger.info("Updated provider", extra={"provider_id": provider_id})
    return {
        "details": provider_config,
        "validatedScopes": validated_scopes,
    }


@router.post("/install")
async def install_provider(
    request: Request,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:providers"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    installed_by = authenticated_entity.email
    try:
        provider_info = await request.json()
    except Exception:
        # If error occurs (likely not JSON), try to get as form data
        form_data = await request.form()
        provider_info = dict(form_data)

    if not provider_info:
        raise HTTPException(status_code=400, detail="No valid data provided")

    # Extract parameters from the provider_info dictionary
    try:
        provider_id = provider_info.pop("provider_id")
        provider_name = provider_info.pop("provider_name")
        provider_type = provider_info.pop("provider_type", None) or provider_id
    except KeyError as e:
        raise HTTPException(
            status_code=400, detail=f"Missing required field: {e.args[0]}"
        )

    provider_unique_id = uuid.uuid4().hex
    logger.info(
        "Installing provider",
        extra={
            "provider_id": provider_id,
            "provider_type": provider_type,
            "tenant_id": tenant_id,
        },
    )
    provider_config = {
        "authentication": provider_info,
        "name": provider_name,
    }
    # we support files as well
    for key, value in provider_config.get("authentication", {}).items():
        if isinstance(value, UploadFile):
            provider_config["authentication"][key] = await value.read()
            provider_config["authentication"][key] = provider_config["authentication"][
                key
            ].decode()

    # Instantiate the provider object and perform installation process
    context_manager = ContextManager(tenant_id=tenant_id)
    try:
        provider = ProvidersFactory.get_provider(
            context_manager, provider_id, provider_type, provider_config
        )
    except (ProviderException, ProviderConfigException) as e:
        raise HTTPException(status_code=400, detail=str(e))

    validated_scopes = validate_scopes(provider)

    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    secret_name = f"{tenant_id}_{provider_type}_{provider_unique_id}"
    secret_manager.write_secret(
        secret_name=secret_name,
        secret_value=json.dumps(provider_config),
    )
    # add the provider to the db
    provider_model = Provider(
        id=provider_unique_id,
        tenant_id=tenant_id,
        name=provider_name,
        type=provider_type,
        installed_by=installed_by,
        installation_time=time.time(),
        configuration_key=secret_name,
        validatedScopes=validated_scopes,
        consumer=provider.is_consumer,
    )
    try:
        session.add(provider_model)
        session.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Provider already installed",
        )
    except Exception as e:
        logger.exception("Failed to add provider to db")
        return JSONResponse(
            status_code=400,
            content={"message": "Failed to install provider", "error": str(e)},
        )

    if provider_model.consumer:
        # Register the provider as a consumer
        try:
            event_subscriber = EventSubscriber.get_instance()
            event_subscriber.add_consumer(provider)
        except Exception:
            logger.exception("Failed to register provider as a consumer")
            # return 200 as the next time Keep will start, it will try to register again

    return JSONResponse(
        status_code=200,
        content={
            "type": provider_type,
            "id": provider_unique_id,
            "details": provider_config,
            "validatedScopes": validated_scopes,
        },
    )


@router.post("/install/oauth2/{provider_type}")
async def install_provider_oauth2(
    provider_type: str,
    provider_info: dict = Body(...),
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:providers"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    installed_by = authenticated_entity.email
    # Extract parameters from the provider_info dictionary
    provider_name = f"{provider_type}-oauth2"

    provider_unique_id = uuid.uuid4().hex
    logger.info(
        "Installing provider",
        extra={
            "provider_id": provider_unique_id,
            "provider_type": provider_type,
            "tenant_id": tenant_id,
        },
    )
    try:
        provider_class = ProvidersFactory.get_provider_class(provider_type)
        provider_info = provider_class.oauth2_logic(**provider_info)
        provider_config = {
            "authentication": provider_info,
            "name": provider_name,
        }
        # Instantiate the provider object and perform installation process
        context_manager = ContextManager(tenant_id=tenant_id)
        provider = ProvidersFactory.get_provider(
            context_manager, provider_unique_id, provider_type, provider_config
        )

        validated_scopes = validate_scopes(provider)

        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        secret_name = f"{tenant_id}_{provider_type}_{provider_unique_id}"
        secret_manager.write_secret(
            secret_name=secret_name,
            secret_value=json.dumps(provider_config),
        )
        # add the provider to the db
        provider = Provider(
            id=provider_unique_id,
            tenant_id=tenant_id,
            name=provider_name,
            type=provider_type,
            installed_by=installed_by,
            installation_time=time.time(),
            configuration_key=secret_name,
            validatedScopes=validated_scopes,
        )
        session.add(provider)
        session.commit()
        return JSONResponse(
            status_code=200,
            content={
                "type": provider_type,
                "id": provider_unique_id,
                "details": provider_config,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{provider_id}/invoke/{method}",
    description="Invoke provider special method",
    status_code=200,
)
def invoke_provider_method(
    provider_id: str,
    method: str,
    method_params: dict,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:providers"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Invoking provider method", extra={"provider_id": provider_id, "method": method}
    )
    provider = session.exec(
        select(Provider).where(
            (Provider.tenant_id == tenant_id) & (Provider.id == provider_id)
        )
    ).one()

    if not provider:
        raise HTTPException(404, detail="Provider not found")

    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    provider_config = secret_manager.read_secret(
        provider.configuration_key, is_json=True
    )
    provider_instance = ProvidersFactory.get_provider(
        context_manager, provider_id, provider.type, provider_config
    )

    func: Callable = getattr(provider_instance, method, None)
    if not func:
        raise HTTPException(400, detail="Method not found")

    try:
        response = func(**method_params)
    except ProviderMethodException as e:
        logger.exception(
            "Failed to invoke method",
            extra={"provider_id": provider_id, "method": method},
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)

    logger.info(
        "Successfully invoked provider method",
        extra={"provider_id": provider_id, "method": method},
    )
    return response


# Webhook related endpoints
@router.post("/install/webhook/{provider_type}/{provider_id}")
def install_provider_webhook(
    provider_type: str,
    provider_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:providers"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    context_manager = ContextManager(
        tenant_id=tenant_id, workflow_id=""  # this is not in a workflow scope
    )
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    provider_config = secret_manager.read_secret(
        f"{tenant_id}_{provider_type}_{provider_id}", is_json=True
    )
    provider = ProvidersFactory.get_provider(
        context_manager, provider_id, provider_type, provider_config
    )
    api_url = config("KEEP_API_URL")
    keep_webhook_api_url = (
        f"{api_url}/alerts/event/{provider_type}?provider_id={provider_id}"
    )
    webhook_api_key = get_or_create_api_key(
        session=session,
        tenant_id=tenant_id,
        created_by="system",
        unique_api_key_id="webhook",
        system_description="Webhooks API key",
    )

    try:
        provider.setup_webhook(tenant_id, keep_webhook_api_url, webhook_api_key, True)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return JSONResponse(status_code=200, content={"message": "webhook installed"})


@router.get("/{provider_type}/webhook")
def get_webhook_settings(
    provider_type: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["read:providers"])
    ),
    session: Session = Depends(get_session),
) -> ProviderWebhookSettings:
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting webhook settings", extra={"provider_type": provider_type})
    api_url = config("KEEP_API_URL")
    keep_webhook_api_url = f"{api_url}/alerts/event/{provider_type}"
    provider_class = ProvidersFactory.get_provider_class(provider_type)
    webhook_api_key = get_or_create_api_key(
        session=session,
        tenant_id=tenant_id,
        created_by="system",
        unique_api_key_id="webhook",
        system_description="Webhooks API key",
    )
    # for cases where we need webhook with auth
    keep_webhook_api_url_with_auth = keep_webhook_api_url.replace(
        "https://", f"https://keep:{webhook_api_key}@"
    )

    try:
        webhookMarkdown = provider_class.webhook_markdown.format(
            keep_webhook_api_url=keep_webhook_api_url,
            api_key=webhook_api_key,
            keep_webhook_api_url_with_auth=keep_webhook_api_url_with_auth,
        )
    except AttributeError:
        webhookMarkdown = None

    logger.info("Got webhook settings", extra={"provider_type": provider_type})
    return ProviderWebhookSettings(
        webhookDescription=provider_class.webhook_description.format(
            keep_webhook_api_url=keep_webhook_api_url,
            api_key=webhook_api_key,
            keep_webhook_api_url_with_auth=keep_webhook_api_url_with_auth,
        ),
        webhookTemplate=provider_class.webhook_template.format(
            keep_webhook_api_url=keep_webhook_api_url,
            api_key=webhook_api_key,
            keep_webhook_api_url_with_auth=keep_webhook_api_url_with_auth,
        ),
        webhookMarkdown=webhookMarkdown,
    )
