import os

import click
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from keep.alert.alert import Alert
from keep.alertmanager.alertmanager import AlertManager
from keep.api.models.step_context import StepContext
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_config_exception import ProviderConfigException

router = APIRouter()


@router.get(
    "",
    description="Get alerts files",
)
def get_alerts_files(
    context: click.Context = Depends(click.get_current_context),
) -> list[str]:
    """
    Iterates the alerts directory and return all the alert files

    Args:
        context (click.Context, optional): _description_. Defaults to Depends(click.get_current_context).

    Returns:
        list[str]: file names
    """
    alertsfiles = []
    alerts_directory = context.params.get("alerts_directory")
    if alerts_directory and os.path.isdir(alerts_directory):
        alertsfiles += os.listdir(alerts_directory)
    elif alerts_directory:
        alertsfiles.append(alerts_directory.split("/")[-1])
    alerts_urls = context.params.get("alert_url")
    for alerts_url in alerts_urls:
        alertsfiles.append(alerts_url.split("/")[-1])

    return alertsfiles


@router.get(
    "/{alerts_file}",
    description="Get alerts file",
)
def get_alert(
    alerts_file: str,
    context: click.Context = Depends(click.get_current_context),
) -> str:
    """Reads a specific alert file

    Args:
        alertsfile (str): _description_
        context (click.Context, optional): _description_. Defaults to Depends(click.get_current_context).

    Raises:
        HTTPException: When the alert file is not found

    Returns:
        str: The content of the alert file
    """
    alerts_directory = context.params.get("alerts_directory")
    try:
        with open("/".join([alerts_directory, alerts_file]), "r") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Alert file not found")


def __get_alert(context: click.Context, alerts_file_id: str, alert_id: str) -> Alert:
    """
    Loads the alert file and returns the alert object

    Args:
        context (click.Context): The click context
        alerts_file_id (str): The alert file id
        alert_id (str): The specific alert id

    Returns:
        Alert: the alert object
    """
    alert_manager = AlertManager()
    alerts_directory = context.params.get("alerts_directory")
    alerts_url = context.params.get("alert_url")
    providers_file = context.params.get("providers_file")
    if alerts_directory:
        alert_path = "/".join([alerts_directory, alerts_file_id])
    else:
        alert_path = alerts_url
    try:
        alerts = alert_manager.get_alerts(alert_path, providers_file)
    except ProviderConfigException as e:
        raise HTTPException(
            status_code=400,
            detail=f"Provider {e.provider_id} is not configured: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    alert = [
        alert
        for alert in alerts
        if alert.alert_id == alert_id and alert.alert_file == alerts_file_id
    ]
    if len(alert) == 0:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    if len(alert) > 1:
        raise HTTPException(
            status_code=502,
            detail="Multiple alerts with the same id within the same file",
        )
    return alert[0]


@router.post(
    "/{alerts_file_id}/alert/{alert_id}/step/{step_id}",
    description="Run step",
)
def run_step(
    alerts_file_name: str,
    alert_id: str,
    step_id: str,
    context: click.Context = Depends(click.get_current_context),
    steps_context: list[StepContext] = [],
) -> JSONResponse:
    """Runs a specific step of a specific alert in the alerts file

    Args:
        alerts_file_id (str): the alert file name
        alert_id (str): the alert id within the alert file
        step_id (str): the step id to execute

    Raises:
        HTTPException: _description_

    Returns:
        JSONResponse: _description_
    """
    alert = __get_alert(context, alerts_file_name, alert_id)

    step = [step for step in alert.alert_steps if step.step_id == step_id]
    if len(step) != 1:
        raise HTTPException(status_code=502, detail="Multiple steps with the same id")

    step = step[0]
    alert.load_context(steps_context)
    alert.run_missing_steps(end_step=step)
    alert.run_step(step)
    context_manager = ContextManager.get_instance()
    step_context = context_manager.get_step_context(step.step_id)
    return jsonable_encoder(step_context)


@router.post(
    "/{alerts_file_id}/alert/{alert_id}/action/{action_name}",
    description="Run action",
)
async def run_action(
    alerts_file_name: str,
    alert_id: str,
    action_name: str,
    click_context: click.Context = Depends(click.get_current_context),
    steps_context: list[StepContext] = [],
) -> list[Alert]:
    alert = __get_alert(click_context, alerts_file_name, alert_id)
    action = [action for action in alert.alert_actions if action.name == action_name]

    if len(action) == 0:
        raise HTTPException(
            status_code=404,
            detail="Action not found in alert, did you use the correct action name?",
        )

    elif len(action) != 1:
        raise HTTPException(status_code=502, detail="Multiple actions with the same id")

    action = action[0]
    alert.load_context(steps_context)
    alert.run_missing_steps()
    action_status, action_error = alert.run_action(action)
    # TODO: add reason why action run or not
    return JSONResponse(
        content={
            "action_run": bool(action_status),
            "action_id": action.name,
            "action_error": action_error,
        }
    )


@router.post(
    "/{alerts_file_id}/alert/{alert_id}",
    description="Run alert",
)
async def run_alert_from_file(
    alerts_file_id: str,
    alert_id: str,
    click_context: click.Context = Depends(click.get_current_context),
    steps_context: list[StepContext] = [],
) -> dict:
    """
    Runs a specific alert in the alerts file

    Args:
        alerts_file_id (str): The alert file
        alert_id (str): The alert id within the alert file

    Returns:
        list[Alert]: _description_
    """
    alert = __get_alert(click_context, alerts_file_id, alert_id)
    alert.load_context(steps_context)
    action_error = alert.run()
    context_manager = ContextManager.get_instance()
    full_context = context_manager.get_full_context()
    return JSONResponse(
        content={
            "steps_context": full_context.get("steps"),
            "action_ran": bool(not any(action_error)),
        }
    )
