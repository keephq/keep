import click
from fastapi import APIRouter, Depends

from keep.alertmanager.alertmanager import AlertManager
from keep.api.core.dependencies import verify_customer
from keep.api.models.db.tenant import TenantApiKey
from keep.providers.providers_factory import ProvidersFactory
from keep.secretmanager.secretmanagerfactory import (
    SecretManagerFactory,
    SecretManagerTypes,
)

router = APIRouter()


@router.get(
    "/",
    description="Get providers",
)
def get_providers(
    tenant: TenantApiKey = Depends(verify_customer),
    context: click.Context = Depends(click.get_current_context),
):
    providers = {}
    alert_manager = AlertManager()
    providers_file = context.params.get("providers_file")
    alerts_directory = context.params.get("alerts_directory")
    alerts_url = context.params.get("alert_url")
    alerts = alert_manager.get_alerts(alerts_directory or alerts_url, providers_file)
    for alert in alerts:
        for step in alert.alert_steps + alert.alert_actions:
            if step.provider.provider_id not in providers:
                providers[step.provider.provider_id] = {
                    "id": step.provider.provider_id,
                    "config": step.provider.config,
                    "type": step.provider.__class__.__name__,
                }
    return list(providers.values())


@router.get(
    "/{provider_type}/{provider_id}/alerts",
    description="Get alerts from a provider",
)
def get_alerts(
    provider_type: str,
    provider_id: str,
    tenant: TenantApiKey = Depends(verify_customer),
):
    # todo: validate provider exists, error handling in general
    # todo: secret manager type from config
    secret_manager = SecretManagerFactory.get_secret_manager(SecretManagerTypes.FILE)
    # todo: secrets convention from config?
    provider_config = secret_manager.read_secret(
        f"{tenant.tenant_id}_{provider_id}", is_json=True
    )
    provider = ProvidersFactory.get_provider(
        provider_id, provider_type, provider_config
    )
    alerts = provider.get_alerts()
    return alerts
