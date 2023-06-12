import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse

from keep.api.core.dependencies import verify_api_key, verify_bearer_token
from keep.api.models.provider import Provider
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
) -> dict[str, Provider]:
    logger.info("Getting installed providers", extra={"tenant_id": tenant_id})
    providers = ProvidersFactory.get_all_providers()
    providers = ProvidersFactory.get_all_providers()
    # TODO: installed providers should be kept in the DB
    #       but for now we just fetch it from the secret manager
    secret_manager = SecretManagerFactory.get_secret_manager()
    installed_providers = secret_manager.list_secrets(prefix=f"{tenant_id}_")
    # TODO: mask the sensitive data
    installed_providers = [
        {
            "name": secret.split("_")[1],
            "details": secret_manager.read_secret(secret.split("/")[-1], is_json=True),
        }
        for secret in installed_providers
        if len(secret.split("_")) == 3  # avoid the installation api key
    ]
    # return list of installed providers
    # TODO: model this
    # TODO: return also metadata (host, etc)
    for p in installed_providers:
        provider_name = p["name"]
        providers[f"{provider_name}_provider"]["installed"] = True
        providers[f"{provider_name}_provider"]["details"] = p["details"]

    return JSONResponse(content=providers)


@router.get(
    "/{provider_type}/{provider_id}/alerts",
    description="Get alerts from a provider",
)
def get_alerts(
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
    # TODO: validate provider exists, error handling in general
    secret_manager = SecretManagerFactory.get_secret_manager()
    # TODO: secrets convention from config?
    provider_config = secret_manager.read_secret(
        f"{tenant_id}_{provider_type}_{provider_id}", is_json=True
    )
    provider = ProvidersFactory.get_provider(
        provider_id, provider_type, provider_config
    )
    return provider.get_alerts()


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
        secret_manager = SecretManagerFactory.get_secret_manager()
        provider_config = secret_manager.read_secret(
            f"{tenant_id}_{provider_type}_{provider_id}", is_json=True
        )
        provider = ProvidersFactory.get_provider(
            provider_id, provider_type, provider_config
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
    description="Get alerts from a provider",
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
    description="Get alerts from a provider",
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
    # TODO: validate provider exists, error handling in general
    secret_manager = SecretManagerFactory.get_secret_manager()
    # TODO: secrets convention from config?
    provider_config = secret_manager.read_secret(
        f"{tenant_id}_{provider_type}_{provider_id}", is_json=True
    )
    provider = ProvidersFactory.get_provider(
        provider_id, provider_type, provider_config
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
    provider = ProvidersFactory.get_provider(
        provider_id, provider_type, provider_config
    )
    try:
        alerts = provider.get_alerts()
        return JSONResponse(status_code=200, content={"alerts": alerts})
    except GetAlertException as e:
        return JSONResponse(status_code=e.status_code, content=e.message)
    except Exception as e:
        return JSONResponse(status_code=400, content=str(e))


@router.post("/install")
async def install_provider(
    provider_info: dict = Body(...),
    tenant_id: str = Depends(verify_bearer_token),
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
    }
    try:
        # Instantiate the provider object and perform installation process
        provider = ProvidersFactory.get_provider(
            provider_id, provider_type, provider_config
        )
        secret_manager = SecretManagerFactory.get_secret_manager()
        provider_config = secret_manager.write_secret(
            secret_name=f"{tenant_id}_{provider_type}_{provider_unique_id}",
            secret_value=json.dumps(provider_config),
        )
        return JSONResponse(
            status_code=200, content={"message": "Provider installed successfully"}
        )

    except GetAlertException as e:
        raise HTTPException(status_code=403, detail=e.message)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
