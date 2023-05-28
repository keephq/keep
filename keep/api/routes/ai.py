import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from keep.api.core.dependencies import verify_api_key
from keep.api.routes.providers import get_alerts, get_alerts_schema
from keep.api.utils.gpt_utils import GptUtils

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateAlert(BaseModel):
    alert: str
    provider_type: str
    provider_id: Optional[str] = None
    repository_context: Optional[dict] = {}


class RepairAlert(BaseModel):
    bad_alert: dict
    error: str
    provider_type: str


@router.post("/create-alert")
def create_alert(body: CreateAlert, tenant_id: str = Depends(verify_api_key)) -> str:
    provider_id = body.provider_id or body.provider_type
    provider_schema = get_alerts_schema(body.provider_type)
    provider_alerts = get_alerts(body.provider_type, provider_id, tenant_id)
    gpt = GptUtils(tenant_id)
    return gpt.generate_alert(
        alert_prompt=body.alert,
        repository_context=body.repository_context,
        alerts_context=provider_alerts,
        schema=provider_schema,
        provider_type=body.provider_type,
    )


@router.post("/repair-alert")
def repair_alert(body: RepairAlert, tenant_id: str = Depends(verify_api_key)):
    gpt = GptUtils(tenant_id)
    return gpt.repair_alert(
        previous_alert=body.bad_alert,
        error=body.error,
        provider_type=body.provider_type,
        schema=get_alerts_schema(body.provider_type),
    )
