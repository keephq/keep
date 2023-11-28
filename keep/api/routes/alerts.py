import base64
import json
import logging
import zlib

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pusher import Pusher
from sqlmodel import Session

from keep.api.core.db import enrich_alert as enrich_alert_db
from keep.api.core.db import get_alerts as get_alerts_from_db
from keep.api.core.db import get_enrichments as get_enrichments_from_db
from keep.api.core.db import get_session
from keep.api.core.dependencies import (
    get_pusher_client,
    get_user_email,
    verify_api_key,
    verify_bearer_token,
    verify_token_or_key,
)
from keep.api.models.alert import AlertDto, DeleteRequestBody, EnrichAlertRequestBody
from keep.api.models.db.alert import Alert
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.providers_factory import ProvidersFactory
from keep.workflowmanager.workflowmanager import WorkflowManager

router = APIRouter()
logger = logging.getLogger(__name__)


def __send_compressed_alerts(
    compressed_alerts_data: str,
    number_of_alerts_in_batch: int,
    tenant_id: str,
    pusher_client: Pusher,
):
    """
    Sends a batch of pulled alerts via pusher.

    Args:
        compressed_alerts_data (str): The compressed data to send.
        number_of_alerts_in_batch (int): The number of alerts in the batch.
        tenant_id (str): The tenant id.
        pusher_client (Pusher): The pusher client.
    """
    logger.info(
        f"Sending batch of pulled alerts via pusher (alerts: {number_of_alerts_in_batch})",
        extra={
            "number_of_alerts": number_of_alerts_in_batch,
        },
    )
    pusher_client.trigger(
        f"private-{tenant_id}",
        "async-alerts",
        compressed_alerts_data,
    )


def pull_alerts_from_providers(
    tenant_id: str, pusher_client: Pusher | None, sync: bool = False
) -> list[AlertDto] | None:
    if pusher_client is None and sync is False:
        raise HTTPException(500, "Cannot pull alerts async when pusher is disabled.")
    all_providers = ProvidersFactory.get_all_providers()
    context_manager = ContextManager(
        tenant_id=tenant_id,
        workflow_id=None,
    )
    installed_providers = ProvidersFactory.get_installed_providers(
        tenant_id=tenant_id, all_providers=all_providers
    )
    logger.info(
        f"{'Asynchronously' if sync is False else 'Synchronously'} pulling alerts from installed providers"
    )
    sync_alerts = []  # if we're running in sync mode
    for provider in installed_providers:
        provider_class = ProvidersFactory.get_provider(
            context_manager=context_manager,
            provider_id=provider.id,
            provider_type=provider.type,
            provider_config=provider.details,
        )
        try:
            logger.info(
                f"Pulling alerts from provider {provider.type} ({provider.id})",
                extra={
                    "provider_type": provider.type,
                    "provider_id": provider.id,
                    "tenant_id": tenant_id,
                },
            )
            alerts = provider_class.get_alerts()
            logger.info(
                f"Pulled alerts from provider {provider.type} ({provider.id})",
                extra={
                    "provider_type": provider.type,
                    "provider_id": provider.id,
                    "tenant_id": tenant_id,
                    "num_of_alerts": len(alerts),
                },
            )

            if alerts:
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
                logger.info(
                    "Enriched pulled alerts",
                    extra={
                        "provider_type": provider.type,
                        "provider_id": provider.id,
                        "tenant_id": tenant_id,
                    },
                )
                if sync:
                    sync_alerts.extend(alerts)
                    logger.info(
                        f"Pulled alerts from provider {provider.type} ({provider.id}) (alerts: {len(alerts)})",
                        extra={
                            "provider_type": provider.type,
                            "provider_id": provider.id,
                            "tenant_id": tenant_id,
                        },
                    )
                    continue

                logger.info("Batch sending pulled alerts via pusher")
                batch_send = []
                previous_compressed_batch = ""
                new_compressed_batch = ""
                number_of_alerts_in_batch = 0
                # tb: this might be too slow in the future and we might need to refactor
                for alert in alerts:
                    alert_dict = alert.dict()
                    batch_send.append(alert_dict)
                    new_compressed_batch = base64.b64encode(
                        zlib.compress(json.dumps(batch_send).encode(), level=9)
                    ).decode()
                    if len(new_compressed_batch) <= 10240:
                        number_of_alerts_in_batch += 1
                        previous_compressed_batch = new_compressed_batch
                    else:
                        __send_compressed_alerts(
                            previous_compressed_batch,
                            number_of_alerts_in_batch,
                            tenant_id,
                            pusher_client,
                        )
                        batch_send = [alert_dict]
                        new_compressed_batch = ""
                        number_of_alerts_in_batch = 1

                # this means we didn't get to this ^ else statement and loop ended
                #   so we need to send the rest of the alerts
                if new_compressed_batch and len(new_compressed_batch) < 10240:
                    __send_compressed_alerts(
                        new_compressed_batch,
                        number_of_alerts_in_batch,
                        tenant_id,
                        pusher_client,
                    )

                logger.info("Sent batch of pulled alerts via pusher")
            logger.info(
                f"Pulled alerts from provider {provider.type} ({provider.id}) (alerts: {len(alerts)})",
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
    if sync is False:
        pusher_client.trigger(f"private-{tenant_id}", "async-done", {})
    logger.info("Fetched alerts from installed providers")
    if sync is True:
        return sync_alerts


@router.get(
    "",
    description="Get alerts",
)
def get_all_alerts(
    background_tasks: BackgroundTasks,
    sync: bool = False,
    tenant_id: str = Depends(verify_token_or_key),
    pusher_client: Pusher | None = Depends(get_pusher_client),
) -> list[AlertDto]:
    logger.info(
        "Fetching alerts from DB",
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
    if sync:
        alerts.extend(pull_alerts_from_providers(tenant_id, pusher_client, sync=True))
    logger.info(
        "Fetched alerts from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )
    if not sync:
        logger.info("Adding task to fetch async alerts from providers")
        background_tasks.add_task(pull_alerts_from_providers, tenant_id, pusher_client)
        logger.info("Added task to async fetch alerts from providers")

    return alerts


@router.delete("", description="Delete alert by name")
def delete_alert(
    delete_alert: DeleteRequestBody,
    tenant_id: str = Depends(verify_bearer_token),
    user_email: str = Depends(get_user_email),
) -> dict[str, str]:
    logger.info(
        "Deleting alert",
        extra={
            "fingerprint": delete_alert.fingerprint,
            "restore": delete_alert.restore,
            "tenant_id": tenant_id,
        },
    )

    enrich_alert_db(
        tenant_id=tenant_id,
        fingerprint=delete_alert.fingerprint,
        enrichments={"deleted": not delete_alert.restore, "assignee": user_email},
    )

    logger.info(
        "Deleted alert successfully",
        extra={
            "tenant_id": tenant_id,
            "restore": delete_alert.restore,
            "fingerprint": delete_alert.fingerprint,
        },
    )
    return {"status": "ok"}


@router.post("/{fingerprint}/assign", description="Assign alert to user")
def assign_alert(
    fingerprint: str,
    unassign: bool = False,
    tenant_id: str = Depends(verify_bearer_token),
    user_email: str = Depends(get_user_email),
) -> dict[str, str]:
    logger.info(
        "Assigning alert",
        extra={
            "fingerprint": fingerprint,
            "tenant_id": tenant_id,
        },
    )

    enrich_alert_db(
        tenant_id=tenant_id,
        fingerprint=fingerprint,
        enrichments={"assignee": user_email if not unassign else None},
    )

    logger.info(
        "Assigned alert successfully",
        extra={
            "tenant_id": tenant_id,
            "fingerprint": fingerprint,
        },
    )
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
            alert_enrichments = get_enrichments_from_db(
                tenant_id=tenant_id, fingerprints=[formatted_event.fingerprint]
            )
            if alert_enrichments:
                # enrich
                for alert_enrichment in alert_enrichments:
                    for enrichment in alert_enrichment.enrichments:
                        # set the enrichment
                        alert.event[enrichment] = alert_enrichment.enrichments[
                            enrichment
                        ]
            try:
                pusher_client.trigger(
                    f"private-{tenant_id}",
                    "async-alerts",
                    base64.b64encode(
                        zlib.compress(json.dumps([alert.event]).encode(), level=9)
                    ).decode(),
                )
            except Exception:
                logger.exception("Failed to push alert to the client")
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
    except Exception:
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
    except Exception:
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
    pusher_client: Pusher = Depends(get_pusher_client),
):
    """
    A generic webhook endpoint that can be used by any provider to send alerts to Keep.

    Args:
        alert (AlertDto | list[AlertDto]): The alert(s) to be sent to Keep.
        bg_tasks (BackgroundTasks): Background tasks handler.
        tenant_id (str, optional): Defaults to Depends(verify_api_key).
        session (Session, optional): Defaults to Depends(get_session).
    """
    if isinstance(alert, AlertDto):
        alert = [alert]
    bg_tasks.add_task(
        handle_formatted_events,
        tenant_id,
        alert[0].source[0] or "keep",
        session,
        alert,
        pusher_client,
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
    all_alerts = get_all_alerts(background_tasks=None, tenant_id=tenant_id, sync=True)
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
