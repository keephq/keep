import click
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from keep.alert.alert import Alert
from keep.alertmanager.alertmanager import AlertManager

router = APIRouter()


@router.get(
    "/",
    description="Get alerts",
)
def get_alerts(
    context: click.Context = Depends(click.get_current_context),
) -> list[Alert]:
    alert_manager = AlertManager()
    alerts_file = context.params.get("alerts_file")
    alerts_url = context.params.get("alert_url")
    providers_file = context.params.get("providers_file")
    alerts = alert_manager.get_alerts(alerts_file or alerts_url, providers_file)
    return alerts


@router.post(
    "/{alert_id}/steps/{step_id}",
    description="Run step",
)
def run_step(
    alert_id: str,
    step_id: str,
    context: click.Context = Depends(click.get_current_context),
) -> list[Alert]:
    alert_manager = AlertManager()
    alerts_file = context.params.get("alerts_file")
    alerts_url = context.params.get("alert_url")
    providers_file = context.params.get("providers_file")
    alerts = alert_manager.get_alerts(alerts_file or alerts_url, providers_file)
    alert = [alert for alert in alerts if alert.alert_id == alert_id]
    if len(alert) != 1:
        raise HTTPException(status_code=502, detail="Multiple alerts with the same id")
    alert = alert[0]

    step = [step for step in alert.alert_steps if step.step_id == step_id]
    if len(step) != 1:
        raise HTTPException(status_code=502, detail="Multiple steps with the same id")
    step = step[0]
    step_output = alert.run_step(step)
    return JSONResponse(content={"step_output": step_output})
