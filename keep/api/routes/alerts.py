import click
from fastapi import APIRouter, Depends

from keep.alert.alert import Alert
from keep.alertmanager.alertmanager import AlertManager

router = APIRouter()


@router.get(
    "/",
    description="Get alerts",
)
def get_providers(
    context: click.Context = Depends(click.get_current_context),
) -> list[Alert]:
    alert_manager = AlertManager()
    alerts_file = context.params.get("alerts_file")
    alerts_url = context.params.get("alert_url")
    providers_file = context.params.get("providers_file")
    alerts = alert_manager.get_alerts(alerts_file or alerts_url, providers_file)
    return alerts
