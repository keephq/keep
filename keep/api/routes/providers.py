import click
from fastapi import APIRouter, Depends

from keep.alertmanager.alertmanager import AlertManager

router = APIRouter()


@router.get(
    "/",
    description="Get providers",
)
def get_providers(context: click.Context = Depends(click.get_current_context)):
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
