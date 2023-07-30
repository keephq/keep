import logging
from dataclasses import asdict
from functools import reduce
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from keep.alertmanager.alertmanager import AlertManager
from keep.alertmanager.alertstore import AlertStore
from keep.api.core.dependencies import verify_bearer_token
from keep.api.models.alertworkflow import WorkflowDTO
from keep.contextmanager.contextmanager import ContextManager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "",
    description="Get alerts workflows",
)
def get_alerts_workflows(
    tenant_id: str = Depends(verify_bearer_token),
) -> list[WorkflowDTO]:
    alertstore = AlertStore()
    alerts = alertstore.get_all_alerts(tenant_id=tenant_id)
    alerts_dto = [
        WorkflowDTO(
            id=alert.alert_id,
            description=alert.alert_description,
            owners=alert.alert_owners,
            interval=alert.alert_interval,
            steps=[asdict(step) for step in alert.alert_steps],
            actions=[asdict(action) for action in alert.alert_actions],
        )
        for alert in alerts
    ]
    return alerts_dto


@router.post(
    "/run/{alert_workflow_id}",
    description="Run an alert workflow",
)
def run_alert_workflow(
    alert_workflow_id: str,
    body: Optional[Dict[Any, Any]] = Body(None),
    tenant_id: str = Depends(verify_bearer_token),
) -> dict:
    # TODO - add alert_workflow_trigger table to track all executions
    logger.info(
        "Running alert workflow", extra={"alert_workflow_id": alert_workflow_id}
    )
    context_manager = ContextManager.get_instance()
    alertstore = AlertStore()
    alertmanager = AlertManager()
    alert = alertstore.get_alert(alert_id=alert_workflow_id, tenant_id=tenant_id)
    # Update the context manager with the alert context
    if body:
        context_manager.update_full_context(**body)

    # Currently, the run alert with interval via API is not supported
    alert.alert_interval = 0
    # Finally, run it
    try:
        errors = alertmanager.run(
            alerts=[alert],
        )
    except Exception as e:
        logger.exception(
            "Failed to run alert workflow",
            extra={"alert_workflow_id": alert_workflow_id},
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run alert workflow {alert_workflow_id}: {e}",
        )
    logger.info(
        "Alert workflow ran successfully",
        extra={"alert_workflow_id": alert_workflow_id},
    )
    if any(errors[0]):
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run alert workflow {alert_workflow_id}: {errors}",
        )
    else:
        # TODO - add some alert_workflow_execution id to track the execution
        return {"alert_workflow_id": alert_workflow_id, "status": "sucess"}
