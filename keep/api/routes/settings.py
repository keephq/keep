from fastapi import APIRouter, Depends
from sqlmodel import Session

from keep.api.core.config import config
from keep.api.core.db import get_session
from keep.api.core.dependencies import verify_bearer_token
from keep.api.models.webhook import WebhookSettings
from keep.api.utils.tenant_utils import get_or_create_api_key

router = APIRouter()


@router.get(
    "/webhook",
    description="Get details about the webhook endpoint (e.g. the API url and an API key)",
)
def webhook_settings(
    tenant_id: str = Depends(verify_bearer_token),
    session: Session = Depends(get_session),
) -> WebhookSettings:
    api_url = config("KEEP_API_URL")
    keep_webhook_api_url = f"{api_url}/alerts/event/{{PROVIDER_TYPE}}"
    webhook_api_key = get_or_create_api_key(
        session=session,
        tenant_id=tenant_id,
        unique_api_key_id="webhook",
        system_description="Webhooks API key",
    )
    return WebhookSettings(webhookApi=keep_webhook_api_url, apiKey=webhook_api_key)
