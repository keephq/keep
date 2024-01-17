# TODO: this whole file needs to get refactored
# mainly: pusher stuff, enrichment stuff and async stuff
import base64
import json
import logging
import zlib

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from opentelemetry import trace
from pusher import Pusher
from sqlmodel import Session

from keep.api.core.config import config
from keep.api.core.db import enrich_alert as enrich_alert_db
from keep.api.core.db import (
    get_alerts_by_fingerprint,
    get_enrichment,
    get_last_alerts,
    get_session,
)
from keep.api.core.dependencies import (
    AuthenticatedEntity,
    AuthVerifier,
    get_pusher_client,
)
from keep.api.models.alert import AlertDto, DeleteRequestBody, EnrichAlertRequestBody
from keep.api.models.db.alert import Alert
from keep.api.utils.email_utils import EmailTemplates, send_email
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.providers_factory import ProvidersFactory
from keep.rulesengine.rulesengine import RulesEngine
from keep.workflowmanager.workflowmanager import WorkflowManager

router = APIRouter()
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def __enrich_alerts(alerts: list[Alert]) -> list[AlertDto]:
    """
    Enriches the alerts with the enrichment data.

    Args:
        alerts (list[Alert]): The alerts to enrich.

    Returns:
        list[AlertDto]: The enriched alerts.
    """
    alerts_dto = []
    with tracer.start_as_current_span("alerts_enrichment"):
        # enrich the alerts with the enrichment data
        for alert in alerts:
            if alert.alert_enrichment:
                alert.event.update(alert.alert_enrichment.enrichments)

            # todo: what is this? :O
            if alert.provider_type == "rules":
                try:
                    alert_dto = AlertDto(**alert.event)
                except Exception:
                    # should never happen but just in case
                    logger.exception(
                        "Failed to parse group alert",
                        extra={
                            "alert": alert,
                        },
                    )
                    continue
            else:
                alert_dto = AlertDto(**alert.event)
                if alert_dto.providerId is None:
                    alert_dto.providerId = alert.provider_id
            alerts_dto.append(alert_dto)
    return alerts_dto


def pull_alerts_from_providers(
    tenant_id: str, pusher_client: Pusher | None, sync: bool = False
) -> list[AlertDto]:
    """
    Pulls alerts from the installed providers.
    tb: THIS FUNCTION NEEDS TO BE REFACTORED!

    Args:
        tenant_id (str): The tenant id.
        pusher_client (Pusher | None): The pusher client.
        sync (bool, optional): Whether the process is sync or not. Defaults to False.

    Raises:
        HTTPException: If the pusher client is None and the process is not sync.

    Returns:
        list[AlertDto]: The pulled alerts.
    """
    if pusher_client is None and sync is False:
        raise HTTPException(500, "Cannot pull alerts async when pusher is disabled.")

    context_manager = ContextManager(
        tenant_id=tenant_id,
        workflow_id=None,
    )

    logger.info(
        f"{'Asynchronously' if sync is False else 'Synchronously'} pulling alerts from installed providers"
    )

    sync_alerts = []  # if we're running in sync mode
    for provider in ProvidersFactory.get_installed_providers(tenant_id=tenant_id):
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
            sorted_provider_alerts_by_fingerprint = (
                provider_class.get_alerts_by_fingerprint(tenant_id=tenant_id)
            )
            logger.info(
                f"Pulled alerts from provider {provider.type} ({provider.id})",
                extra={
                    "provider_type": provider.type,
                    "provider_id": provider.id,
                    "tenant_id": tenant_id,
                    "number_of_fingerprints": len(
                        sorted_provider_alerts_by_fingerprint.keys()
                    ),
                },
            )

            if sorted_provider_alerts_by_fingerprint:
                last_alerts = [
                    alerts[0]
                    for alerts in sorted_provider_alerts_by_fingerprint.values()
                ]
                if sync:
                    sync_alerts.extend(last_alerts)
                    logger.info(
                        f"Pulled alerts from provider {provider.type} ({provider.id}) (alerts: {len(sorted_provider_alerts_by_fingerprint)})",
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
                for alert in last_alerts:
                    alert_dict = alert.dict()
                    batch_send.append(alert_dict)
                    new_compressed_batch = base64.b64encode(
                        zlib.compress(json.dumps(batch_send).encode(), level=9)
                    ).decode()
                    if len(new_compressed_batch) <= 10240:
                        number_of_alerts_in_batch += 1
                        previous_compressed_batch = new_compressed_batch
                    else:
                        pusher_client.trigger(
                            f"private-{tenant_id}",
                            "async-alerts",
                            previous_compressed_batch,
                        )
                        batch_send = [alert_dict]
                        new_compressed_batch = ""
                        number_of_alerts_in_batch = 1

                # this means we didn't get to this ^ else statement and loop ended
                #   so we need to send the rest of the alerts
                if new_compressed_batch and len(new_compressed_batch) < 10240:
                    pusher_client.trigger(
                        f"private-{tenant_id}",
                        "async-alerts",
                        new_compressed_batch,
                    )
                logger.info("Sent batch of pulled alerts via pusher")
            logger.info(
                f"Pulled alerts from provider {provider.type} ({provider.id}) (alerts: {len(sorted_provider_alerts_by_fingerprint)})",
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
    return sync_alerts


@router.get(
    "",
    description="Get last alerts occurrence",
)
def get_all_alerts(
    background_tasks: BackgroundTasks,
    sync: bool = False,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
    pusher_client: Pusher | None = Depends(get_pusher_client),
) -> list[AlertDto]:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching alerts from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )
    db_alerts = get_last_alerts(tenant_id=tenant_id)
    enriched_alerts_dto = __enrich_alerts(db_alerts)
    logger.info(
        "Fetched alerts from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    if sync:
        enriched_alerts_dto.extend(
            pull_alerts_from_providers(tenant_id, pusher_client, sync=True)
        )
    else:
        logger.info("Adding task to async fetch alerts from providers")
        background_tasks.add_task(pull_alerts_from_providers, tenant_id, pusher_client)
        logger.info("Added task to async fetch alerts from providers")

    return enriched_alerts_dto


@router.get("/{fingerprint}/history", description="Get alert history")
def get_alert_history(
    fingerprint: str,
    provider_id: str | None = None,
    provider_type: str | None = None,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
) -> list[AlertDto]:
    logger.info(
        "Fetching alert history",
        extra={
            "fingerprint": fingerprint,
            "tenant_id": authenticated_entity.tenant_id,
        },
    )
    db_alerts = get_alerts_by_fingerprint(
        tenant_id=authenticated_entity.tenant_id, fingerprint=fingerprint
    )
    enriched_alerts_dto = __enrich_alerts(db_alerts)

    if provider_id is not None and provider_type is not None:
        try:
            installed_provider = ProvidersFactory.get_installed_provider(
                tenant_id=authenticated_entity.tenant_id,
                provider_id=provider_id,
                provider_type=provider_type,
            )
            pulled_alerts_history = installed_provider.get_alerts_by_fingerprint(
                tenant_id=authenticated_entity.tenant_id
            ).get(fingerprint, [])
            enriched_alerts_dto.extend(pulled_alerts_history)
        except Exception:
            logger.warn(
                "Failed to pull alerts history from installed provider",
                extra={
                    "provider_id": provider_id,
                    "provider_type": provider_type,
                    "tenant_id": authenticated_entity.tenant_id,
                },
            )

    logger.info(
        "Fetched alert history",
        extra={
            "tenant_id": authenticated_entity.tenant_id,
            "fingerprint": fingerprint,
        },
    )
    return enriched_alerts_dto


@router.delete("", description="Delete alert by name")
def delete_alert(
    delete_alert: DeleteRequestBody,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["delete:alert"])),
) -> dict[str, str]:
    tenant_id = authenticated_entity.tenant_id
    user_email = authenticated_entity.email

    logger.info(
        "Deleting alert",
        extra={
            "fingerprint": delete_alert.fingerprint,
            "restore": delete_alert.restore,
            "lastReceived": delete_alert.lastReceived,
            "tenant_id": tenant_id,
        },
    )

    deleted_last_received = []  # the last received(s) that are deleted
    assignees_last_receievd = {}  # the last received(s) that are assigned to someone
    enrichment = get_enrichment(tenant_id, delete_alert.fingerprint)
    if enrichment:
        deleted_last_received = enrichment.enrichments.get("deleted", [])
        assignees_last_receievd = enrichment.enrichments.get("assignees", {})
        # TODO: this is due to legacy deleted field that was a bool, remove in the future
        if isinstance(deleted_last_received, bool):
            deleted_last_received = []

    if (
        delete_alert.restore is True
        and delete_alert.lastReceived in deleted_last_received
    ):
        deleted_last_received.remove(delete_alert.lastReceived)
    elif delete_alert.restore is False:
        deleted_last_received.append(delete_alert.lastReceived)

    if delete_alert.lastReceived not in assignees_last_receievd:
        assignees_last_receievd[delete_alert.lastReceived] = user_email

    enrich_alert_db(
        tenant_id=tenant_id,
        fingerprint=delete_alert.fingerprint,
        enrichments={
            "deleted": deleted_last_received,
            "assignees": assignees_last_receievd,
        },
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


@router.post(
    "/{fingerprint}/assign/{last_received}", description="Assign alert to user"
)
def assign_alert(
    fingerprint: str,
    last_received: str,
    unassign: bool = False,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["write:alert"])),
) -> dict[str, str]:
    tenant_id = authenticated_entity.tenant_id
    user_email = authenticated_entity.email
    logger.info(
        "Assigning alert",
        extra={
            "fingerprint": fingerprint,
            "tenant_id": tenant_id,
        },
    )

    assignees_last_receievd = {}  # the last received(s) that are assigned to someone
    enrichment = get_enrichment(tenant_id, fingerprint)
    if enrichment:
        assignees_last_receievd = enrichment.enrichments.get("assignees", {})

    if unassign:
        assignees_last_receievd.pop(last_received, None)
    else:
        assignees_last_receievd[last_received] = user_email

    enrich_alert_db(
        tenant_id=tenant_id,
        fingerprint=fingerprint,
        enrichments={"assignees": assignees_last_receievd},
    )

    try:
        if not unassign:  # if we're assigning the alert to someone, send email
            logger.info("Sending assign alert email to user")
            # TODO: this should be changed to dynamic url but we don't know what's the frontend URL
            keep_platform_url = config(
                "KEEP_PLATFORM_URL", default="https://platform.keephq.dev"
            )
            url = f"{keep_platform_url}/alerts?fingerprint={fingerprint}"
            send_email(
                to_email=user_email,
                template_id=EmailTemplates.ALERT_ASSIGNED_TO_USER,
                url=url,
            )
            logger.info("Sent assign alert email to user")
    except Exception as e:
        logger.exception(
            "Failed to send email to user",
            extra={
                "error": str(e),
                "tenant_id": tenant_id,
                "user_email": user_email,
            },
        )

    logger.info(
        "Assigned alert successfully",
        extra={
            "tenant_id": tenant_id,
            "fingerprint": fingerprint,
        },
    )
    return {"status": "ok"}


# this is super important function and does three things:
# 1. adds the alerts to the DB
# 2. runs workflows based on the alerts
# 3. runs the rules engine
# TODO: add appropriate logs, trace and all of that so we can track errors
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
            alert_event_copy = {**alert.event}
            alert_enrichment = get_enrichment(
                tenant_id=tenant_id, fingerprint=formatted_event.fingerprint
            )
            if alert_enrichment:
                for enrichment in alert_enrichment.enrichments:
                    # set the enrichment
                    alert_event_copy[enrichment] = alert_enrichment.enrichments[
                        enrichment
                    ]
            try:
                pusher_client.trigger(
                    f"private-{tenant_id}",
                    "async-alerts",
                    base64.b64encode(
                        zlib.compress(
                            json.dumps([AlertDto(**alert_event_copy).dict()]).encode(),
                            level=9,
                        )
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

    # Now we need to run the rules engine
    try:
        rules_engine = RulesEngine(tenant_id=tenant_id)
        grouped_alerts = rules_engine.run_rules(formatted_events)
        # if new grouped alerts were created, we need to push them to the client
        if grouped_alerts:
            logger.info("Adding group alerts to the workflow manager queue")
            workflow_manager.insert_events(tenant_id, grouped_alerts)
            logger.info("Added group alerts to the workflow manager queue")
            # Now send the grouped alerts to the client
            logger.info("Sending grouped alerts to the client")
            for grouped_alert in grouped_alerts:
                try:
                    pusher_client.trigger(
                        f"private-{tenant_id}",
                        "async-alerts",
                        base64.b64encode(
                            zlib.compress(
                                json.dumps([grouped_alert.dict()]).encode(), level=9
                            )
                        ).decode(),
                    )
                except Exception:
                    logger.exception("Failed to push alert to the client")
            logger.info("Sent grouped alerts to the client")
    except Exception:
        logger.exception(
            "Failed to run rules engine",
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
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["write:alert"])),
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
    tenant_id = authenticated_entity.tenant_id
    if isinstance(alert, AlertDto):
        alert = [alert]

    for _alert in alert:
        # if not source, set it to keep
        if not _alert.source:
            _alert.source = ["keep"]
    bg_tasks.add_task(
        handle_formatted_events,
        tenant_id,
        alert[0].source[0],
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
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["write:alert"])),
    session: Session = Depends(get_session),
    pusher_client: Pusher = Depends(get_pusher_client),
) -> dict[str, str]:
    tenant_id = authenticated_entity.tenant_id
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
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
    session: Session = Depends(get_session),
) -> AlertDto:
    tenant_id = authenticated_entity.tenant_id
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
        raise HTTPException(status_code=404, detail="Alert not found")


@router.post(
    "/enrich",
    description="Enrich an alert",
)
def enrich_alert(
    enrich_data: EnrichAlertRequestBody,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["write:alert"])),
) -> dict[str, str]:
    tenant_id = authenticated_entity.tenant_id
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
