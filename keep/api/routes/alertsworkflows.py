import logging
from functools import reduce

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from keep.alertmanager.alertstore import AlertStore
from keep.api.core.db import get_session
from keep.api.core.dependencies import verify_bearer_token
from keep.api.models.alertworkflow import WorkflowDTO

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
            services=alert.services,
            interval=alert.interval,
            steps=alert.steps,
            actions=alert.actions,
        )
        for alert in alerts
    ]
    return alerts_dto
