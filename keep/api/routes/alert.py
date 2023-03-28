import tempfile

import click
import yaml
from fastapi import APIRouter, Depends, Request

from keep.alertmanager.alertmanager import AlertManager

router = APIRouter()


@router.post(
    "/",
    description="Save and run alert",
)
async def run_alert(
    request: Request,
    context: click.Context = Depends(click.get_current_context),
    alert_name=None,
):
    alert_manager = AlertManager()
    raw_body = await request.body()
    providers_file = context.params.get("providers_file")
    # no need to save the alert to a file, just run it
    if not alert_name:
        with tempfile.NamedTemporaryFile() as alert_file:
            yaml.safe_load(raw_body)
            alert_file.write(raw_body)
            alert_file.flush()
            alert_manager.run(alert_file.name, providers_file)
