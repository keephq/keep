import os

import click
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

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
