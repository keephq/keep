import json
import logging
import time
import uuid
from typing import Optional

import jwt
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from keep.api.core.config import config
from keep.api.core.db import get_session
from keep.api.core.dependencies import (
    get_user_email,
    verify_api_key,
    verify_bearer_token,
)
from keep.api.models.db.provider import Provider
from keep.api.models.webhook import ProviderWebhookSettings
from keep.api.utils.tenant_utils import get_or_create_api_key
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.provider_exceptions import GetAlertException
from keep.providers.providers_factory import ProvidersFactory
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "",
)
def get_providers(
    tenant_id: str = Depends(verify_bearer_token),
):
    logger.info("Getting installed providers", extra={"tenant_id": tenant_id})
    providers = ProvidersFactory.get_all_providers()
    installed_providers = ProvidersFactory.get_installed_providers(
        tenant_id, providers, include_details=False
    )

    try:
        return {
            "providers": providers,
            "installed_providers": installed_providers,
        }
    except Exception:
        logger.exception("Failed to get providers")
        return {"providers": providers, "installed_providers": []}


@router.get(
    "/{provider_type}/{provider_id}/configured-alerts",
    description="Get alerts configuration from a provider",
)
def get_alerts_configuration(
    provider_type: str,
    provider_id: str,
    tenant_id: str = Depends(verify_api_key),
) -> list:
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
    tenant_id: str = Depends(verify_api_key),
) -> list:
    try:
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


@router.post(
    "/{provider_type}/{provider_id}/alerts",
    description="Push new alerts to the provider",
)
def add_alert(
    provider_type: str,
    provider_id: str,
    alert: dict,
    alert_id: Optional[str] = None,
    tenant_id: str = Depends(verify_api_key),
) -> JSONResponse:
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
    tenant_id: str = Depends(verify_bearer_token),
) -> JSONResponse:
    # Extract parameters from the provider_info dictionary
    # For now, we support only 1:1 provider_type:provider_id
    # In the future, we might want to support multiple providers of the same type
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
    tenant_id: str = Depends(verify_bearer_token),
    session: Session = Depends(get_session),
):
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
        except Exception as exc:
            logger.exception("Failed to delete the provider secret")
            pass
        # delete the provider anyway
        session.delete(provider)
        session.commit()
    except Exception as exc:
        # TODO: handle it better
        logger.exception("Failed to delete the provider secret")
        pass
    logger.info("Deleted provider", extra={"provider_id": provider_id})
    return JSONResponse(status_code=200, content={"message": "deleted"})


@router.post("/install")
async def install_provider(
    provider_info: dict = Body(...),
    tenant_id: str = Depends(verify_bearer_token),
    session: Session = Depends(get_session),
    installed_by: str = Depends(get_user_email),
):
    # Extract parameters from the provider_info dictionary
    provider_id = provider_info.pop("provider_id")
    provider_name = provider_info.pop("provider_name")
    provider_type = provider_info.pop("provider_type", None) or provider_id

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

    # Instantiate the provider object and perform installation process
    context_manager = ContextManager(tenant_id=tenant_id)
    provider = ProvidersFactory.get_provider(
        context_manager, provider_id, provider_type, provider_config
    )

    provider_scopes = provider.validate_scopes()
    mandatory_scopes_validated = True
    if provider.PROVIDER_SCOPES and provider_scopes:
        # All of the mandatory scopes must be validated
        for scope in provider.PROVIDER_SCOPES:
            if scope.mandatory and (
                scope.name not in provider_scopes or provider_scopes[scope.name] != True
            ):
                mandatory_scopes_validated = False
                break
    # Otherwise we fail the installation
    if not mandatory_scopes_validated:
        raise HTTPException(
            status_code=412,
            detail=provider_scopes,
        )

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
        scopes=provider_scopes,
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


@router.post("/install/oauth2/{provider_type}")
async def install_provider_oauth2(
    provider_type: str,
    provider_info: dict = Body(...),
    tenant_id: str = Depends(verify_bearer_token),
    session: Session = Depends(get_session),
    installed_by: str = Depends(get_user_email),
):
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


# Webhook related


@router.post("/install/webhook/{provider_type}/{provider_id}")
def install_provider_webhook(
    provider_type: str,
    provider_id: str,
    tenant_id: str = Depends(verify_bearer_token),
    session: Session = Depends(get_session),
):
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
        unique_api_key_id="webhook",
        system_description="Webhooks API key",
    )
    provider.setup_webhook(tenant_id, keep_webhook_api_url, webhook_api_key, True)
    return JSONResponse(status_code=200, content={"message": "webhook installed"})


@router.get("/{provider_type}/webhook")
def get_webhook_settings(
    provider_type: str,
    tenant_id: str = Depends(verify_bearer_token),
    session: Session = Depends(get_session),
) -> ProviderWebhookSettings:
    logger.info("Getting webhook settings", extra={"provider_type": provider_type})
    api_url = config("KEEP_API_URL")
    keep_webhook_api_url = f"{api_url}/alerts/event/{provider_type}"
    provider_class = ProvidersFactory.get_provider_class(provider_type)
    webhook_api_key = get_or_create_api_key(
        session=session,
        tenant_id=tenant_id,
        unique_api_key_id="webhook",
        system_description="Webhooks API key",
    )
    logger.info("Got webhook settings", extra={"provider_type": provider_type})
    return ProviderWebhookSettings(
        webhookDescription=provider_class.webhook_description,
        webhookTemplate=provider_class.webhook_template.format(
            keep_webhook_api_url=keep_webhook_api_url, api_key=webhook_api_key
        ),
    )
