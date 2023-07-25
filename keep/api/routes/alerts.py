import logging
from functools import reduce

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from keep.api.core.db import get_session
from keep.api.core.dependencies import verify_bearer_token
from keep.api.models.alert import AlertDto
from keep.api.models.db.alert import Alert
from keep.providers.providers_factory import ProvidersFactory

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "",
    description="Get alerts",
)
def get_alerts(
    provider_type: str = None,
    provider_id: str = None,
    tenant_id: str = Depends(verify_bearer_token),
    # session: Session = Depends(get_session),
) -> list[AlertDto]:
    # if provider_id:
    #     if not provider_type:
    #         raise HTTPException(
    #             400, "provider_type is required when provider_id is set"
    #         )
    alerts = []
    installed_providers = ProvidersFactory.get_installed_providers(tenant_id=tenant_id)
    for provider in installed_providers:
        provider_type, provider_id, provider_config = provider.values()
        provider = ProvidersFactory.get_provider(
            provider_id=provider_id,
            provider_type=provider_type,
            provider_config=provider_config,
        )
        try:
            alerts.extend(provider.get_alerts())
        except Exception:
            logger.exception(
                "Could not fetch alerts from provider",
                extra={"provider_id": provider_id, "provider_type": provider_type},
            )
            pass
    return alerts


@router.post(
    "/event/{provider_type}", description="Receive an alert event from a provider"
)
def receive_event(
    provider_type: str,
    event: dict,
    provider_id: str | None = None,
    tenant_id: str = Depends(verify_bearer_token),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    logger.info(
        "Received event", extra={"provider_type": provider_type, "event": event}
    )
    provider_class = ProvidersFactory.get_provider_class(provider_type)
    try:
        logger.info(
            "Creating new alert in DB",
            extra={"provider_type": provider_type, "event": event},
        )
        # Each provider should implement a format_alert method that returns an AlertDto
        # object that will later be returned to the client.
        formatted_event = provider_class.format_alert(event)
        alert = Alert(
            tenant_id=tenant_id,
            provider_type=provider_type,
            event=formatted_event.dict(),
            provider_id=provider_id,
        )
        session.add(alert)
        session.commit()
        logger.info(
            "New alert created successfully",
            extra={"provider_type": provider_type, "event": event},
        )
        return {"status": "ok"}
    except Exception as e:
        logger.warn("Failed to create new alert", extra={"error": str(e)})
        return {"status": "failed"}
