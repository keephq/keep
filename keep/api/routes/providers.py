import json
from typing import Optional

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from keep.api.core.dependencies import decode_auth0_token, verify_customer
from keep.api.models.db.tenant import TenantApiKey
from keep.providers.base.provider_exceptions import GetAlertException
from keep.providers.providers_factory import ProvidersFactory
from keep.secretmanager.secretmanagerfactory import (
    SecretManagerFactory,
    SecretManagerTypes,
)

router = APIRouter()


@router.get(
    "",
)
def get_installed_providers(
    token: Optional[dict] = Depends(decode_auth0_token),
) -> list:
    # TODO: installed providers should be kept in the DB
    #       but for now we just fetch it from the secret manager
    tenant_id = token.get("keep_tenant_id")
    secret_manager = SecretManagerFactory.get_secret_manager(SecretManagerTypes.GCP)
    installed_providers = secret_manager.list_secrets(prefix=f"{tenant_id}_")
    # TODO: mask the sensitive data
    installed_providers = [
        {
            "name": secret.name.split("_")[1],
            "details": secret_manager.read_secret(
                secret.name.split("/")[-1], is_json=True
            ),
        }
        for secret in installed_providers
    ]
    # return list of installed providers
    # TODO: model this
    # TODO: return also metadata (host, etc)
    return JSONResponse(content=installed_providers)


@router.get(
    "/{provider_type}/{provider_id}/alerts",
    description="Get alerts from a provider",
)
def get_alerts(
    provider_type: str,
    provider_id: str,
    tenant: TenantApiKey = Depends(verify_customer),
) -> list:
    # todo: validate provider exists, error handling in general
    # todo: secret manager type from config
    secret_manager = SecretManagerFactory.get_secret_manager(SecretManagerTypes.GCP)
    # todo: secrets convention from config?
    provider_config = secret_manager.read_secret(
        f"{tenant.tenant_id}_{provider_type}_{provider_id}", is_json=True
    )
    provider = ProvidersFactory.get_provider(
        provider_id, provider_type, provider_config
    )
    return provider.get_alerts()


@router.get(
    "/{provider_type}/schema",
    description="Get alerts from a provider",
)
def get_alerts_schema(
    provider_type: str,
) -> dict:
    provider = ProvidersFactory.get_provider_class(provider_type)
    return JSONResponse(provider.get_alert_format_description())


@router.post(
    "/{provider_type}/{provider_id}/alerts",
    description="Get alerts from a provider",
)
def add_alert(
    provider_type: str,
    provider_id: str,
    alert: dict,
    alert_id: Optional[str] = None,
    tenant: TenantApiKey = Depends(verify_customer),
) -> JSONResponse:
    # todo: validate provider exists, error handling in general
    # todo: secret manager type from config
    secret_manager = SecretManagerFactory.get_secret_manager(SecretManagerTypes.GCP)
    # todo: secrets convention from config?
    provider_config = secret_manager.read_secret(
        f"{tenant.tenant_id}_{provider_type}_{provider_id}", is_json=True
    )
    provider = ProvidersFactory.get_provider(
        provider_id, provider_type, provider_config
    )
    try:
        provider.deploy_alert(alert, alert_id)
        return JSONResponse(status_code=200, content={"message": "deployed"})
    except Exception as e:
        return JSONResponse(status_code=400, content=e.args[0])


@router.post(
    "/test",
    description="Test a provider's alert retrieval",
)
def test_provider(
    provider_info: dict = Body(...),
    token: Optional[dict] = Depends(decode_auth0_token),
) -> JSONResponse:
    # Extract parameters from the provider_info dictionary
    # For now, we support only 1:1 provider_type:provider_id
    # In the future, we might want to support multiple providers of the same type
    provider_id = provider_info.pop("provider_id")
    provider_type = provider_info.pop("provider_type", None) or provider_id
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
        return JSONResponse(status_code=403, content=e.message)
    except Exception as e:
        return JSONResponse(status_code=400, content=e.args[0])


@router.post("/install")
async def install_provider(
    provider_info: dict = Body(...),
    token: Optional[dict] = Depends(decode_auth0_token),
):
    # Extract parameters from the provider_info dictionary
    tenant_id = token.get("keep_tenant_id")
    provider_id = provider_info.pop("provider_id")
    provider_type = provider_info.pop("provider_type", None) or provider_id
    provider_config = {
        "authentication": provider_info,
    }
    try:
        # Instantiate the provider object and perform installation process
        provider = ProvidersFactory.get_provider(
            provider_id, provider_type, provider_config
        )
        secret_manager = SecretManagerFactory.get_secret_manager(SecretManagerTypes.GCP)
        # todo: how to manage secrets in OSS
        provider_config = secret_manager.write_secret(
            secret_name=f"{tenant_id}_{provider_type}_{provider_id}",
            secret_value=json.dumps(provider_config),
        )
        return JSONResponse(
            status_code=200, content={"message": "Provider installed successfully"}
        )

    except GetAlertException as e:
        raise HTTPException(status_code=403, detail=e.message)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
