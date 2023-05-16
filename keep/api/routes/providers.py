from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from keep.api.core.dependencies import verify_customer
from keep.api.models.db.tenant import TenantApiKey
from keep.providers.providers_factory import ProvidersFactory
from keep.secretmanager.secretmanagerfactory import (
    SecretManagerFactory,
    SecretManagerTypes,
)

router = APIRouter()


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
        return JSONResponse(status_code=500, content=e.args[0])


@router.get("")
def get_providers():
    """List of static providers that can be installed

    Returns:
        _type_: _description_
    """
    return JSONResponse(
        content=[
            {
                "id": "aws",
                "name": "AWS",
            },
            {
                "id": "gcp",
                "name": "GCP",
            },
        ]
    )
