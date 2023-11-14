import gzip
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pusher import Pusher
from sqlmodel import Session

from keep.api.core.db import enrich_alert as enrich_alert_db
from keep.api.core.db import get_alerts as get_alerts_from_db
from keep.api.core.db import get_enrichments as get_enrichments_from_db
from keep.api.core.db import get_session
from keep.api.core.dependencies import (
    get_pusher_client,
    verify_api_key,
    verify_bearer_token,
    verify_token_or_key,
)
from keep.api.models.alert import AlertDto, DeleteRequestBody, EnrichAlertRequestBody
from keep.api.models.db.alert import Alert, AlertEnrichment
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.providers_factory import ProvidersFactory
from keep.workflowmanager.workflowmanager import WorkflowManager

router = APIRouter()
logger = logging.getLogger(__name__)


def get_alerts_from_providers_async(tenant_id: str, pusher_client: Pusher):
    all_providers = ProvidersFactory.get_all_providers()
    context_manager = ContextManager(
        tenant_id=tenant_id,
        workflow_id=None,
    )
    installed_providers = ProvidersFactory.get_installed_providers(
        tenant_id=tenant_id, all_providers=all_providers
    )
    logger.info("Asyncronusly fetching alerts from installed providers")
    for provider in installed_providers:
        provider_class = ProvidersFactory.get_provider(
            context_manager=context_manager,
            provider_id=provider.id,
            provider_type=provider.type,
            provider_config=provider.details,
        )
        try:
            logger.info(
                "Fetching alerts from installed provider",
                extra={
                    "provider_type": provider.type,
                    "provider_id": provider.id,
                    "tenant_id": tenant_id,
                },
            )
            alerts = provider_class.get_alerts()
            # enrich also the pulled alerts:
            pulled_alerts_fingerprints = list(
                set([alert.fingerprint for alert in alerts])
            )
            pulled_alerts_enrichments = get_enrichments_from_db(
                tenant_id=tenant_id, fingerprints=pulled_alerts_fingerprints
            )
            logger.info(
                "Enriching pulled alerts",
                extra={
                    "provider_type": provider.type,
                    "provider_id": provider.id,
                    "tenant_id": tenant_id,
                },
            )
            for alert_enrichment in pulled_alerts_enrichments:
                for alert in alerts:
                    if alert_enrichment.alert_fingerprint == alert.fingerprint:
                        # enrich
                        for enrichment in alert_enrichment.enrichments:
                            # set the enrichment
                            setattr(
                                alert,
                                enrichment,
                                alert_enrichment.enrichments[enrichment],
                            )

            # chunks of 10
            logger.info("Batch sending alerts via pusher")
            max_alerts_per_trigger = 5
            for i in range(0, len(alerts), max_alerts_per_trigger):
                pusher_client.trigger(
                    f"private-{tenant_id}",
                    "async-alerts",
                    [alert.dict() for alert in alerts][i : i + max_alerts_per_trigger],
                )
            logger.info("Sent batch of alerts via pusher")

            logger.info(
                "Enriched pulled alerts",
                extra={
                    "provider_type": provider.type,
                    "provider_id": provider.id,
                    "tenant_id": tenant_id,
                },
            )
            logger.info(
                "Fetched alerts from installed provider",
                extra={
                    "provider_type": provider.type,
                    "provider_id": provider.id,
                    "tenant_id": tenant_id,
                },
            )
        except Exception as e:
            logger.warn(
                f"Could not fetch alerts from provider due to {e}",
                extra={
                    "provider_id": provider.id,
                    "provider_type": provider.type,
                    "tenant_id": tenant_id,
                },
            )
            pass
    pusher_client.trigger(f"private-{tenant_id}", "async-done", {})
    logger.info("Asyncronusly fetched alerts from installed providers")


@router.get(
    "",
    description="Get alerts",
)
def get_all_alerts(
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(verify_token_or_key),
    pusher_client: Pusher = Depends(get_pusher_client),
) -> list[AlertDto]:
    logger.info(
        "Fetching alerts DB",
        extra={
            "tenant_id": tenant_id,
        },
    )
    db_alerts = get_alerts_from_db(tenant_id=tenant_id)
    # enrich the alerts with the enrichment data
    for alert in db_alerts:
        if alert.alert_enrichment:
            alert.event.update(alert.alert_enrichment.enrichments)
    alerts = [AlertDto(**alert.event) for alert in db_alerts]
    logger.info(
        "Fetched alerts DB",
        extra={
            "tenant_id": tenant_id,
        },
    )
    logger.info("Adding task to fetch alerts from providers async")
    background_tasks.add_task(get_alerts_from_providers_async, tenant_id, pusher_client)
    logger.info("Added task to fetch alerts from providers async")
    return alerts


@router.delete("", description="Delete alert by name")
def delete_alert(
    delete_alert: DeleteRequestBody,
    tenant_id: str = Depends(verify_bearer_token),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    logger.info(
        "Deleting alert",
        extra={
            "alert_name": delete_alert.alert_name,
            "tenant_id": tenant_id,
        },
    )
    delete_query = f"""
    DELETE FROM {Alert.__tablename__}
    WHERE alert.tenant_id = :tenant_id AND JSON_EXTRACT(alert.event, '$.name') = :alert_name
"""
    alert_name = delete_alert.alert_name.strip("'").strip('"')
    session.execute(delete_query, {"tenant_id": tenant_id, "alert_name": alert_name})
    session.commit()
    return {"status": "ok"}


def handle_formatted_events(
    tenant_id,
    provider_type,
    session: Session,
    formatted_events: list[AlertDto],
    pusher_client: Pusher,
    provider_id: str | None = None,
):
    logger.info(
        "Asyncronusly adding new alerts to the DB",
        extra={
            "provider_type": provider_type,
            "num_of_alerts": len(formatted_events),
            "provider_id": provider_id,
            "tenant_id": tenant_id,
        },
    )
    try:
        for formatted_event in formatted_events:
            formatted_event.pushed = True
            alert = Alert(
                tenant_id=tenant_id,
                provider_type=provider_type,
                event=formatted_event.dict(),
                provider_id=provider_id,
                fingerprint=formatted_event.fingerprint,
            )
            session.add(alert)
            formatted_event.event_id = alert.id
            pusher_client.trigger(
                f"private-{tenant_id}",
                "async-alerts",
                [alert.event],
            )
        session.commit()
        logger.info(
            "Asyncronusly added new alerts to the DB",
            extra={
                "provider_type": provider_type,
                "num_of_alerts": len(formatted_events),
                "provider_id": provider_id,
                "tenant_id": tenant_id,
            },
        )
    except Exception as e:
        logger.exception(
            "Failed to push alerts to the DB",
            extra={
                "provider_type": provider_type,
                "num_of_alerts": len(formatted_events),
                "provider_id": provider_id,
                "tenant_id": tenant_id,
            },
        )
    try:
        # Now run any workflow that should run based on this alert
        # TODO: this should publish event
        workflow_manager = WorkflowManager.get_instance()
        # insert the events to the workflow manager process queue
        logger.info("Adding events to the workflow manager queue")
        workflow_manager.insert_events(tenant_id, formatted_events)
        logger.info("Added events to the workflow manager queue")
    except Exception as e:
        logger.exception(
            "Failed to run workflows based on alerts",
            extra={
                "provider_type": provider_type,
                "num_of_alerts": len(formatted_events),
                "provider_id": provider_id,
                "tenant_id": tenant_id,
            },
        )


@router.post(
    "/event",
    description="Receive a generic alert event",
    response_model=AlertDto | list[AlertDto],
    status_code=201,
)
async def receive_generic_event(
    alert: AlertDto | list[AlertDto],
    bg_tasks: BackgroundTasks,
    tenant_id: str = Depends(verify_api_key),
    session: Session = Depends(get_session),
):
    """
    A generic webhook endpoint that can be used by any provider to send alerts to Keep.

    Args:
        alert (AlertDto | list[AlertDto]): The alert(s) to be sent to Keep.
        bg_tasks (BackgroundTasks): Background tasks handler.
        tenant_id (str, optional): Defaults to Depends(verify_api_key).
        session (Session, optional): Defaults to Depends(get_session).
    """
    bg_tasks.add_task(
        handle_formatted_events,
        tenant_id,
        alert.source[0] or "generic",
        session,
        alert,
    )
    return alert


@router.post(
    "/event/{provider_type}", description="Receive an alert event from a provider"
)
async def receive_event(
    provider_type: str,
    request: Request,
    bg_tasks: BackgroundTasks,
    provider_id: str | None = None,
    tenant_id: str = Depends(verify_api_key),
    session: Session = Depends(get_session),
    pusher_client: Pusher = Depends(get_pusher_client),
) -> dict[str, str]:
    provider_class = ProvidersFactory.get_provider_class(provider_type)
    # if this request is just to confirm the sns subscription, return ok
    # TODO: think of a more elegant way to do this
    # Get the raw body as bytes
    body = await request.body()
    # Parse the raw body
    body = provider_class.parse_event_raw_body(body)
    # Start process the event
    # Attempt to parse as JSON if the content type is not text/plain
    # content_type = request.headers.get("Content-Type")
    # For example, SNS events (https://docs.aws.amazon.com/sns/latest/dg/SendMessageToHttp.prepare.html)
    try:
        event = json.loads(body.decode())
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # else, process the event
    logger.info(
        "Handling event",
        extra={
            "provider_type": provider_type,
            "provider_id": provider_id,
            "tenant_id": tenant_id,
        },
    )
    provider_class = ProvidersFactory.get_provider_class(provider_type)
    try:
        # Each provider should implement a format_alert method that returns an AlertDto
        # object that will later be returned to the client.
        logger.info(
            f"Trying to format alert with {provider_type}",
            extra={
                "provider_type": provider_type,
                "provider_id": provider_id,
                "tenant_id": tenant_id,
            },
        )
        # tb: if we want to have fingerprint_fields configured by the user, format_alert
        #   needs to be called from an initalized provider instance instead of a static method.
        formatted_events = provider_class.format_alert(event)

        if isinstance(formatted_events, AlertDto):
            formatted_events = [formatted_events]

        logger.info(
            f"Formatted alerts with {provider_type}",
            extra={
                "provider_type": provider_type,
                "provider_id": provider_id,
                "tenant_id": tenant_id,
            },
        )
        # If the format_alert does not return an AlertDto object, it means that the event
        # should not be pushed to the client.
        if formatted_events:
            bg_tasks.add_task(
                handle_formatted_events,
                tenant_id,
                provider_type,
                session,
                formatted_events,
                pusher_client,
                provider_id,
            )
        logger.info(
            "Handled event successfully",
            extra={
                "provider_type": provider_type,
                "provider_id": provider_id,
                "tenant_id": tenant_id,
            },
        )
        return {"status": "ok"}
    except Exception as e:
        logger.exception(
            "Failed to handle event", extra={"error": str(e), "tenant_id": tenant_id}
        )
        raise HTTPException(400, "Failed to handle event")


@router.get(
    "/{fingerprint}",
    description="Get alert by fingerprint",
)
def get_alert(
    fingerprint: str,
    tenant_id: str = Depends(verify_token_or_key),
    session: Session = Depends(get_session),
) -> AlertDto:
    logger.info(
        "Fetching alert",
        extra={
            "fingerprint": fingerprint,
            "tenant_id": tenant_id,
        },
    )
    # TODO: once pulled alerts will be in the db too, this should be changed
    all_alerts = get_all_alerts(tenant_id=tenant_id)
    alert = list(filter(lambda alert: alert.fingerprint == fingerprint, all_alerts))
    if alert:
        return alert[0]
    else:
        return HTTPException(status_code=404, detail="Alert not found")


@router.post(
    "/enrich",
    description="Enrich an alert",
)
def enrich_alert(
    enrich_data: EnrichAlertRequestBody,
    tenant_id: str = Depends(verify_token_or_key),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    logger.info(
        "Enriching alert",
        extra={
            "fingerprint": enrich_data.fingerprint,
            "tenant_id": tenant_id,
        },
    )

    try:
        enrich_alert_db(
            tenant_id=tenant_id,
            fingerprint=enrich_data.fingerprint,
            enrichments=enrich_data.enrichments,
        )

        logger.info(
            "Alert enriched successfully",
            extra={"fingerprint": enrich_data.fingerprint, "tenant_id": tenant_id},
        )
        return {"status": "ok"}

    except Exception as e:
        logger.exception("Failed to enrich alert", extra={"error": str(e)})
        return {"status": "failed"}
