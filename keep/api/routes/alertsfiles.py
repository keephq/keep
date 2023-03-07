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


@router.post(
    "/{alerts_file_id}/alert/{alert_id}/step/{step_id}",
    description="Run step",
)
def run_step(
    alerts_file_id: str,
    alert_id: str,
    step_id: str,
    context: click.Context = Depends(click.get_current_context),
) -> list[Alert]:
    alert_manager = AlertManager()
    alerts_file = context.params.get("alerts_file")
    alerts_url = context.params.get("alert_url")
    providers_file = context.params.get("providers_file")
    alerts = alert_manager.get_alerts(alerts_file or alerts_url, providers_file)
    alert = [
        alert
        for alert in alerts
        if alert.alert_id == alert_id and alert.alert_file == alerts_file_id
    ]
    if len(alert) != 1:
        raise HTTPException(
            status_code=502,
            detail="Multiple alerts with the same id within the same file",
        )
    alert = alert[0]

    step = [step for step in alert.alert_steps if step.step_id == step_id]
    if len(step) != 1:
        raise HTTPException(status_code=502, detail="Multiple steps with the same id")

    step = step[0]
    step_output = alert.run_step(step)
    return JSONResponse(content={"step_output": step_output})
