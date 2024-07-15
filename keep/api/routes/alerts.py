import base64
import hashlib
import hmac
import json
import logging
import os
from typing import Optional

import celpy
from arq import ArqRedis
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.responses import JSONResponse
from pusher import Pusher

from keep.api.arq_worker import get_pool
from keep.api.bl.enrichments import EnrichmentsBl
from keep.api.core.config import config
from keep.api.core.db import get_alert_audit as get_alert_audit_db
from keep.api.core.db import get_alerts_by_fingerprint, get_enrichment, get_last_alerts
from keep.api.core.dependencies import (
    AuthenticatedEntity,
    AuthVerifier,
    get_pusher_client,
)
from keep.api.core.elastic import ElasticClient
from keep.api.models.alert import AlertDto, DeleteRequestBody, EnrichAlertRequestBody
from keep.api.models.db.alert import AlertActionType
from keep.api.models.search_alert import SearchAlertsRequest
from keep.api.tasks.process_event_task import process_event
from keep.api.utils.email_utils import EmailTemplates, send_email
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.providers.providers_factory import ProvidersFactory
from keep.searchengine.searchengine import SearchEngine

router = APIRouter()
logger = logging.getLogger(__name__)

REDIS = os.environ.get("REDIS", "false") == "true"


@router.get(
    "",
    description="Get last alerts occurrence",
)
def get_all_alerts(
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
) -> list[AlertDto]:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching alerts from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )
    db_alerts = get_last_alerts(tenant_id=tenant_id)
    enriched_alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
    logger.info(
        "Fetched alerts from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

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
        tenant_id=authenticated_entity.tenant_id, fingerprint=fingerprint, limit=1000
    )
    enriched_alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)

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
            logger.warning(
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


@router.delete("", description="Delete alert by finerprint and last received time")
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

    # If we enriched before, get the enrichment
    enrichment = get_enrichment(tenant_id, delete_alert.fingerprint)
    if enrichment:
        deleted_last_received = enrichment.enrichments.get("deletedAt", [])
        assignees_last_receievd = enrichment.enrichments.get("assignees", {})

    if (
        delete_alert.restore is True
        and delete_alert.lastReceived in deleted_last_received
    ):
        # Restore deleted alert
        deleted_last_received.remove(delete_alert.lastReceived)
    elif (
        delete_alert.restore is False
        and delete_alert.lastReceived not in deleted_last_received
    ):
        # Delete the alert if it's not already deleted (wtf basically, shouldn't happen)
        deleted_last_received.append(delete_alert.lastReceived)

    if delete_alert.lastReceived not in assignees_last_receievd:
        # auto-assign the deleting user to the alert
        assignees_last_receievd[delete_alert.lastReceived] = user_email

    # overwrite the enrichment
    enrichment_bl = EnrichmentsBl(tenant_id)
    enrichment_bl.enrich_alert(
        fingerprint=delete_alert.fingerprint,
        enrichments={
            "deletedAt": deleted_last_received,
            "assignees": assignees_last_receievd,
        },
        action_type=AlertActionType.DELETE_ALERT,
        action_description=f"Alert deleted by {user_email}",
        action_callee=user_email,
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

    enrichment_bl = EnrichmentsBl(tenant_id)
    enrichment_bl.enrich_alert(
        fingerprint=fingerprint,
        enrichments={"assignees": assignees_last_receievd},
        action_type=AlertActionType.ACKNOWLEDGE,
        action_description=f"Alert assigned to {user_email}",
        action_callee=user_email,
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


@router.post(
    "/event",
    description="Receive a generic alert event",
    response_model=AlertDto | list[AlertDto],
    status_code=202,
)
async def receive_generic_event(
    event: AlertDto | list[AlertDto] | dict,
    bg_tasks: BackgroundTasks,
    request: Request,
    fingerprint: str | None = None,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["write:alert"])),
):
    """
    A generic webhook endpoint that can be used by any provider to send alerts to Keep.

    Args:
        alert (AlertDto | list[AlertDto]): The alert(s) to be sent to Keep.
        bg_tasks (BackgroundTasks): Background tasks handler.
        tenant_id (str, optional): Defaults to Depends(verify_api_key).
        session (Session, optional): Defaults to Depends(get_session).
    """
    if REDIS:
        redis: ArqRedis = await get_pool()
        await redis.enqueue_job(
            "process_event",
            authenticated_entity.tenant_id,
            None,
            None,
            fingerprint,
            authenticated_entity.api_key_name,
            request.state.trace_id,
            event,
        )
    else:
        bg_tasks.add_task(
            process_event,
            {},
            authenticated_entity.tenant_id,
            None,
            None,
            fingerprint,
            authenticated_entity.api_key_name,
            request.state.trace_id,
            event,
        )
    return Response(status_code=202)


# https://learn.netdata.cloud/docs/alerts-&-notifications/notifications/centralized-cloud-notifications/webhook#challenge-secret
@router.get(
    "/event/netdata",
    description="Helper function to complete Netdata webhook challenge",
)
async def webhook_challenge():
    token = Request.query_params.get("token").encode("ascii")
    KEY = "keep-netdata-webhook-integration"

    # creates HMAC SHA-256 hash from incomming token and your consumer secret
    sha256_hash_digest = hmac.new(
        KEY.encode(), msg=token, digestmod=hashlib.sha256
    ).digest()

    # construct response data with base64 encoded hash
    response = {
        "response_token": "sha256="
        + base64.b64encode(sha256_hash_digest).decode("ascii")
    }

    return json.dumps(response)


@router.post(
    "/event/{provider_type}",
    description="Receive an alert event from a provider",
    status_code=202,
)
async def receive_event(
    provider_type: str,
    event: dict | bytes,
    bg_tasks: BackgroundTasks,
    request: Request,
    provider_id: str | None = None,
    fingerprint: str | None = None,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["write:alert"])),
) -> dict[str, str]:
    trace_id = request.state.trace_id
    provider_class = ProvidersFactory.get_provider_class(provider_type)
    # Parse the raw body
    event = provider_class.parse_event_raw_body(event)

    if REDIS:
        redis: ArqRedis = await get_pool()
        await redis.enqueue_job(
            "process_event",
            authenticated_entity.tenant_id,
            provider_type,
            provider_id,
            fingerprint,
            authenticated_entity.api_key_name,
            trace_id,
            event,
        )
    else:
        bg_tasks.add_task(
            process_event,
            {},
            authenticated_entity.tenant_id,
            provider_type,
            provider_id,
            fingerprint,
            authenticated_entity.api_key_name,
            trace_id,
            event,
        )
    return Response(status_code=202)


@router.get(
    "/{fingerprint}",
    description="Get alert by fingerprint",
)
def get_alert(
    fingerprint: str,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
) -> AlertDto:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching alert",
        extra={
            "fingerprint": fingerprint,
            "tenant_id": tenant_id,
        },
    )
    all_alerts = get_all_alerts(authenticated_entity=authenticated_entity)
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
    pusher_client: Pusher = Depends(get_pusher_client),
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["write:alert"])),
    dispose_on_new_alert: Optional[bool] = Query(
        False, description="Dispose on new alert"
    ),
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
        enrichement_bl = EnrichmentsBl(tenant_id)
        # Shahar: TODO, change to the specific action type, good enough for now
        if "status" in enrich_data.enrichments:
            action_type = (
                AlertActionType.MANUAL_RESOLVE
                if enrich_data.enrichments["status"] == "resolved"
                else AlertActionType.MANUAL_STATUS_CHANGE
            )
            action_description = f"Alert status was changed to {enrich_data.enrichments['status']} by {authenticated_entity.email}"
        elif "note" in enrich_data.enrichments:
            action_type = AlertActionType.COMMENT
            action_description = f"Comment added by {authenticated_entity.email} - {enrich_data.enrichments['note']}"
        elif "ticket_url" in enrich_data.enrichments:
            action_type = AlertActionType.TICKET_ASSIGNED
            action_description = f"Ticket assigned by {authenticated_entity.email} - {enrich_data.enrichments['ticket_url']}"
        else:
            action_type = AlertActionType.GENERIC_ENRICH
            action_description = f"Alert enriched by {authenticated_entity.email} - {enrich_data.enrichments}"
        enrichement_bl.enrich_alert(
            fingerprint=enrich_data.fingerprint,
            enrichments=enrich_data.enrichments,
            action_type=action_type,
            action_callee=authenticated_entity.email,
            action_description=action_description,
            dispose_on_new_alert=dispose_on_new_alert,
        )
        # get the alert with the new enrichment
        alert = get_alerts_by_fingerprint(
            authenticated_entity.tenant_id, enrich_data.fingerprint, limit=1
        )
        if not alert:
            logger.warning(
                "Alert not found", extra={"fingerprint": enrich_data.fingerprint}
            )
            return {"status": "failed"}

        enriched_alerts_dto = convert_db_alerts_to_dto_alerts(alert)
        # push the enriched alert to the elasticsearch
        try:
            logger.info("Pushing enriched alert to elasticsearch")
            elastic_client = ElasticClient(tenant_id)
            elastic_client.index_alert(
                alert=enriched_alerts_dto[0],
            )
            logger.info("Pushed enriched alert to elasticsearch")
        except Exception:
            logger.exception("Failed to push alert to elasticsearch")
            pass
        # use pusher to push the enriched alert to the client
        if pusher_client:
            logger.info("Telling client to poll alerts")
            try:
                pusher_client.trigger(
                    f"private-{tenant_id}",
                    "poll-alerts",
                    "{}",
                )
                logger.info("Told client to poll alerts")
            except Exception:
                logger.exception("Failed to tell client to poll alerts")
                pass
        logger.info(
            "Alert enriched successfully",
            extra={"fingerprint": enrich_data.fingerprint, "tenant_id": tenant_id},
        )
        return {"status": "ok"}

    except Exception as e:
        logger.exception("Failed to enrich alert", extra={"error": str(e)})
        return {"status": "failed"}


@router.post(
    "/search",
    description="Search alerts",
)
async def search_alerts(
    search_request: SearchAlertsRequest,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
) -> list[AlertDto]:
    tenant_id = authenticated_entity.tenant_id
    try:
        logger.info(
            "Searching alerts",
            extra={"tenant_id": tenant_id},
        )
        search_engine = SearchEngine(tenant_id)
        filtered_alerts = search_engine.search_alerts(search_request.query)
        logger.info(
            "Searched alerts",
            extra={"tenant_id": tenant_id},
        )
        return filtered_alerts
    except celpy.celparser.CELParseError as e:
        logger.warning("Failed to parse the search query", extra={"error": str(e)})
        return JSONResponse(
            status_code=400,
            content={
                "error": "Failed to parse the search query",
                "query": search_request.query,
                "line": e.line,
                "column": e.column,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to search alerts", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Failed to search alerts")


@router.get(
    "/{fingerprint}/audit",
    description="Get alert enrichment",
)
def get_alert_audit(
    fingerprint: str,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching alert audit",
        extra={
            "fingerprint": fingerprint,
            "tenant_id": tenant_id,
        },
    )
    alert_audit = get_alert_audit_db(tenant_id, fingerprint)
    if not alert_audit:
        raise HTTPException(status_code=404, detail="Alert not found")

    grouped_events = []
    previous_event = None
    count = 1

    for event in alert_audit:
        if previous_event and (
            event.user_id == previous_event.user_id
            and event.action == previous_event.action
            and event.description == previous_event.description
        ):
            count += 1
        else:
            if previous_event:
                if count > 1:
                    previous_event.description += f" x{count}"
                grouped_events.append(previous_event.dict())
            previous_event = event
            count = 1

    # Add the last event
    if previous_event:
        if count > 1:
            previous_event.description += f" x{count}"
        grouped_events.append(previous_event.dict())

    return grouped_events
