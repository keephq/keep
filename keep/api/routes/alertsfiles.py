import os

import click
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from keep.alert.alert import Alert
from keep.alertmanager.alertmanager import AlertManager

router = APIRouter()


@router.get(
    "",
    description="Get alerts files",
)
def get_alerts_files(
    context: click.Context = Depends(click.get_current_context),
) -> list[str]:
    alertsfiles = []
    alerts_file = context.params.get("alerts_file")
    if alerts_file and os.path.isdir(alerts_file):
        alertsfiles += os.listdir(alerts_file)
    elif alerts_file:
        alertsfiles.append(alerts_file.split("/")[-1])
    alerts_urls = context.params.get("alert_url")
    for alerts_url in alerts_urls:
        alertsfiles.append(alerts_url.split("/")[-1])

    return alertsfiles


@router.get(
    "/{alertsfile}",
    description="Get alerts file",
)
def get_alert(
    alertsfile: str,
    context: click.Context = Depends(click.get_current_context),
) -> list[Alert]:
    alert_manager = AlertManager()
    alerts_file = context.params.get("alerts_file")
    alerts_url = context.params.get("alert_url")
    providers_file = context.params.get("providers_file")
    alerts = alert_manager.get_alerts(alerts_file or alerts_url, providers_file)
    alerts = [alert for alert in alerts if alert.alert_file == alertsfile]
    if not alerts:
        raise HTTPException(status_code=404, detail="Alert file not found")
    return alerts
