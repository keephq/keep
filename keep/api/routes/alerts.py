import base64
import concurrent.futures
import hashlib
import hmac
import json
import logging
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from typing import List, Optional

import celpy
from arq import ArqRedis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pusher import Pusher
from sqlalchemy_utils import UUIDType
from sqlmodel import Session

from keep.api.arq_pool import get_pool
from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.consts import KEEP_ARQ_QUEUE_BASIC
from keep.api.core.alerts import (
    get_alert_facets,
    get_alert_facets_data,
    get_alert_potential_facet_fields,
    query_last_alerts,
)
from keep.api.core.cel_to_sql.sql_providers.base import CelToSqlException
from keep.api.core.config import config
from keep.api.core.db import dismiss_error_alerts as dismiss_error_alerts_db
from keep.api.core.db import enrich_alerts_with_incidents
from keep.api.core.db import get_alert_audit as get_alert_audit_db
from keep.api.core.db import (
    get_alerts_by_fingerprint,
    get_alerts_metrics_by_provider,
    get_enrichment,
)
from keep.api.core.db import get_error_alerts as get_error_alerts_db
from keep.api.core.db import (
    get_last_alert_by_fingerprint,
    get_last_alerts,
    get_session,
    is_all_alerts_resolved,
)
from keep.api.core.dependencies import extract_generic_body, get_pusher_client
from keep.api.core.elastic import ElasticClient
from keep.api.core.metrics import running_tasks_by_process_gauge, running_tasks_gauge
from keep.api.models.alert import (
    AlertDto,
    AlertErrorDto,
    AlertStatus,
    DeleteRequestBody,
    DismissAlertRequest,
    EnrichAlertNoteRequestBody,
    EnrichAlertRequestBody,
    IncidentStatus,
    UnEnrichAlertRequestBody,
)
from keep.api.models.alert_audit import AlertAuditDto
from keep.api.models.db.alert import ActionType
from keep.api.models.db.rule import ResolveOn
from keep.api.models.facet import FacetOptionsQueryDto
from keep.api.models.query import QueryDto
from keep.api.models.search_alert import SearchAlertsRequest
from keep.api.models.time_stamp import TimeStampFilter
from keep.api.routes.preset import pull_data_from_providers
from keep.api.tasks.process_event_task import process_event
from keep.api.utils.email_utils import EmailTemplates, send_email
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.api.utils.time_stamp_helpers import get_time_stamp_filter
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.providers.providers_factory import ProvidersFactory
from keep.searchengine.searchengine import SearchEngine
from keep.workflowmanager.workflowmanager import WorkflowManager

router = APIRouter()
logger = logging.getLogger(__name__)

REDIS = os.environ.get("REDIS", "false") == "true"
EVENT_WORKERS = int(config("KEEP_EVENT_WORKERS", default=5, cast=int))

# Create dedicated threadpool
process_event_executor = ThreadPoolExecutor(
    max_workers=EVENT_WORKERS, thread_name_prefix="process_event_worker"
)


@router.post(
    "/facets/options",
    description="Query alert facet options. Accepts dictionary where key is facet id and value is cel to query facet",
)
def fetch_alert_facet_options(
    facet_options_query: FacetOptionsQueryDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
) -> dict:
    tenant_id = authenticated_entity.tenant_id

    logger.info(
        "Fetching alert facets from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    try:
        facet_options = get_alert_facets_data(
            tenant_id=tenant_id, facet_options_query=facet_options_query
        )
    except CelToSqlException as e:
        logger.exception(
            f'Error parsing CEL expression "{facet_options_query.cel}". {str(e)}'
        )
        raise HTTPException(
            status_code=400,
            detail=f"Error parsing CEL expression: {facet_options_query.cel}",
        ) from e

    logger.info(
        "Fetched alert facets from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return facet_options


@router.get(
    "/facets",
    description="Get alert facets",
)
def fetch_alert_facets(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
) -> list:
    tenant_id = authenticated_entity.tenant_id

    logger.info(
        "Fetching alert facets from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    facets = get_alert_facets(tenant_id=tenant_id)

    logger.info(
        "Fetched alert facets from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return facets


@router.get(
    "/facets/fields",
    description="Get potential fields for alert facets",
)
def fetch_alert_facet_fields(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
) -> list:
    tenant_id = authenticated_entity.tenant_id

    logger.info(
        "Fetching alert facet fields from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    fields = get_alert_potential_facet_fields(tenant_id=tenant_id)

    logger.info(
        "Fetched alert facet fields from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )
    return fields


@router.post(
    "/query",
    description="Get last alerts occurrence",
)
def query_alerts(
    request: Request,
    query: QueryDto,
    bg_tasks: BackgroundTasks,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
):
    # Gathering alerts may take a while and we don't care if it will finish before we return the response.
    # In the worst case, gathered alerts will be pulled in the next request.
    # This approach is not good. We should continuesly pull alerts without relying on whether request is done or not.
    bg_tasks.add_task(
        pull_data_from_providers,
        authenticated_entity.tenant_id,
        request.state.trace_id,
    )

    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching alerts from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    try:
        db_alerts, total_count = query_last_alerts(
            tenant_id=tenant_id,
            limit=query.limit,
            offset=query.offset,
            cel=query.cel,
            sort_by=query.sort_by,
            sort_dir=query.sort_dir,
        )
    except CelToSqlException as e:
        logger.exception(f'Error parsing CEL expression "{query.cel}". {str(e)}')
        raise HTTPException(
            status_code=400, detail=f"Error parsing CEL expression: {query.cel}"
        ) from e

    enriched_alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
    logger.info(
        "Fetched alerts from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return {
        "limit": query.limit,
        "offset": query.offset,
        "count": total_count,
        "results": enriched_alerts_dto,
    }


@router.get(
    "",
    description="Get last alerts occurrence",
)
def get_all_alerts(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
    limit: int = 1000,
) -> list[AlertDto]:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching alerts from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )
    db_alerts = get_last_alerts(tenant_id=tenant_id, limit=limit)
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
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
) -> list[AlertDto]:
    logger.info(
        "Fetching alert history",
        extra={
            "fingerprint": fingerprint,
            "tenant_id": authenticated_entity.tenant_id,
        },
    )
    db_alerts = get_alerts_by_fingerprint(
        tenant_id=authenticated_entity.tenant_id,
        fingerprint=fingerprint,
        limit=1000,
        with_alert_instance_enrichment=True,
    )
    enriched_alerts_dto = convert_db_alerts_to_dto_alerts(
        db_alerts, with_alert_instance_enrichment=True
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
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["delete:alert"])
    ),
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
    enrichment_bl.enrich_entity(
        fingerprint=delete_alert.fingerprint,
        enrichments={
            "deletedAt": deleted_last_received,
            "assignees": assignees_last_receievd,
        },
        action_type=ActionType.DELETE_ALERT,
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
    authenticated_entity: AuthenticatedEntity = Depends(
        # @tb: this is read because NOC users can also assign alerts to themselves
        # anyway, this function needs to be refactored
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
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
    status = "acknowledged"
    enrichment = get_enrichment(tenant_id, fingerprint)
    if enrichment:
        assignees_last_receievd = enrichment.enrichments.get("assignees", {})
        status = enrichment.enrichments.get("status", "acknowledged")
    if unassign:
        assignees_last_receievd.pop(last_received, None)
    else:
        assignees_last_receievd[last_received] = user_email

    enrichments = {"assignees": assignees_last_receievd, "status": status}

    enrichment_bl = EnrichmentsBl(tenant_id)
    enrichment_bl.enrich_entity(
        fingerprint=fingerprint,
        enrichments=enrichments,
        action_type=ActionType.ACKNOWLEDGE,
        action_description=f"Alert assigned to {user_email}, status: {status}",
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


def discard_future(
    trace_id: str,
    future: Future,
    running_tasks: set,
    started_time: float,
):
    try:
        running_tasks.discard(future)
        running_tasks_gauge.dec()
        running_tasks_by_process_gauge.labels(pid=os.getpid()).dec()

        # Log any exception that occurred in the future
        try:
            exception = future.exception()
            if exception:
                logger.error(
                    "Task failed with exception",
                    extra={
                        "trace_id": trace_id,
                        "error": str(exception),
                        "processing_time": time.time() - started_time,
                    },
                )
            else:
                logger.info(
                    "Task completed",
                    extra={
                        "processing_time": time.time() - started_time,
                        "trace_id": trace_id,
                    },
                )
        except concurrent.futures.CancelledError:
            logger.error(
                "Task was cancelled",
                extra={
                    "trace_id": trace_id,
                    "processing_time": time.time() - started_time,
                },
            )

    except Exception:
        # Make sure we always decrement both counters even if something goes wrong
        running_tasks_gauge.dec()
        running_tasks_by_process_gauge.labels(pid=os.getpid()).dec()
        logger.exception(
            "Error in discard_future callback",
            extra={
                "trace_id": trace_id,
            },
        )


def create_process_event_task(
    tenant_id: str,
    provider_type: str | None,
    provider_id: str | None,
    fingerprint: str,
    api_key_name: str | None,
    trace_id: str,
    event: AlertDto | list[AlertDto] | dict,
    running_tasks: set,
) -> str:
    logger.info("Adding task", extra={"trace_id": trace_id})
    started_time = time.time()
    running_tasks_gauge.inc()  # Increase total counter
    running_tasks_by_process_gauge.labels(
        pid=os.getpid()
    ).inc()  # Increase process counter
    future = process_event_executor.submit(
        process_event,
        {},  # ctx
        tenant_id,
        provider_type,
        provider_id,
        fingerprint,
        api_key_name,
        trace_id,
        event,
    )
    running_tasks.add(future)
    future.add_done_callback(
        lambda task: discard_future(trace_id, task, running_tasks, started_time)
    )

    logger.info("Task added", extra={"trace_id": trace_id})
    return str(id(future))


@router.post(
    "/event",
    description="Receive a generic alert event",
    response_model=AlertDto | list[AlertDto],
    status_code=202,
)
async def receive_generic_event(
    event: AlertDto | list[AlertDto] | dict,
    request: Request,
    provider_id: str | None = None,
    fingerprint: str | None = None,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:alert"])
    ),
):
    """
    A generic webhook endpoint that can be used by any provider to send alerts to Keep.

    Args:
        alert (AlertDto | list[AlertDto]): The alert(s) to be sent to Keep.
        bg_tasks (BackgroundTasks): Background tasks handler.
        tenant_id (str, optional): Defaults to Depends(verify_api_key).
    """
    running_tasks: set = request.state.background_tasks
    if REDIS:
        redis: ArqRedis = await get_pool()
        job = await redis.enqueue_job(
            "async_process_event",
            authenticated_entity.tenant_id,
            None,
            provider_id,
            fingerprint,
            authenticated_entity.api_key_name,
            request.state.trace_id,
            event,
            _queue_name=KEEP_ARQ_QUEUE_BASIC,
        )
        logger.info(
            "Enqueued job",
            extra={
                "job_id": job.job_id,
                "tenant_id": authenticated_entity.tenant_id,
                "queue": KEEP_ARQ_QUEUE_BASIC,
            },
        )
        task_name = job.job_id
    else:
        task_name = create_process_event_task(
            authenticated_entity.tenant_id,
            None,
            provider_id,
            fingerprint,
            authenticated_entity.api_key_name,
            request.state.trace_id,
            event,
            running_tasks,
        )
    return JSONResponse(content={"task_name": task_name}, status_code=202)


# https://learn.netdata.cloud/docs/alerts-&-notifications/notifications/centralized-cloud-notifications/webhook#challenge-secret
@router.get(
    "/event/netdata",
    description="Helper function to complete Netdata webhook challenge",
)
async def webhook_challenge():
    try:
        token = Request.query_params.get("token").encode("ascii")
    except Exception as e:
        logger.exception("Failed to get token", extra={"error": str(e)})
        raise HTTPException(status_code=400, detail="Bad request: failed to get token")
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
    request: Request,
    provider_id: str | None = None,
    fingerprint: str | None = None,
    event=Depends(extract_generic_body),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:alert"])
    ),
) -> dict[str, str]:
    trace_id = request.state.trace_id
    running_tasks: set = request.state.background_tasks
    provider_class = None
    try:
        t = time.time()
        logger.debug(f"Getting provider class for {provider_type}")
        provider_class = ProvidersFactory.get_provider_class(provider_type)
        logger.debug(
            "Got provider class",
            extra={
                "provider_type": provider_type,
                "time": time.time() - t,
            },
        )
    except ModuleNotFoundError:
        raise HTTPException(
            status_code=400, detail=f"Provider {provider_type} not found"
        )
    if not provider_class:
        raise HTTPException(
            status_code=400, detail=f"Provider {provider_type} not found"
        )

    # Parse the raw body
    t = time.time()
    logger.debug("Parsing event raw body")
    event = provider_class.parse_event_raw_body(event)
    logger.debug("Parsed event raw body", extra={"time": time.time() - t})
    if REDIS:
        redis: ArqRedis = await get_pool()
        job = await redis.enqueue_job(
            "async_process_event",
            authenticated_entity.tenant_id,
            provider_type,
            provider_id,
            fingerprint,
            authenticated_entity.api_key_name,
            trace_id,
            event,
            _queue_name=KEEP_ARQ_QUEUE_BASIC,
        )
        logger.info(
            "Enqueued job",
            extra={
                "job_id": job.job_id,
                "tenant_id": authenticated_entity.tenant_id,
                "queue": KEEP_ARQ_QUEUE_BASIC,
            },
        )
        task_name = job.job_id
    else:
        task_name = create_process_event_task(
            authenticated_entity.tenant_id,
            provider_type,
            provider_id,
            fingerprint,
            authenticated_entity.api_key_name,
            trace_id,
            event,
            running_tasks,
        )
    return JSONResponse(content={"task_name": task_name}, status_code=202)


@router.get(
    "/{fingerprint}",
    description="Get alert by fingerprint",
)
def get_alert(
    fingerprint: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
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


@router.post("/enrich/note", description="Enrich an alert note")
def enrich_alert_note(
    enrich_data: EnrichAlertNoteRequestBody,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])  # also NOC
    ),
) -> dict[str, str]:
    logger.info("Enriching alert note", extra={"fingerprint": enrich_data.fingerprint})
    enriched_data = EnrichAlertRequestBody(
        enrichments={"note": enrich_data.note},
        fingerprint=enrich_data.fingerprint,
    )
    return _enrich_alert(
        enriched_data,
        authenticated_entity=authenticated_entity,
        dispose_on_new_alert=True,
    )


@router.post(
    "/enrich",
    description="Enrich an alert",
)
def enrich_alert(
    enrich_data: EnrichAlertRequestBody,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:alert"])
    ),
    dispose_on_new_alert: Optional[bool] = Query(
        False, description="Dispose on new alert"
    ),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    if (
        "dismissed" in enrich_data.enrichments
        and enrich_data.enrichments["dismissed"].lower() == "true"
    ):
        enrich_data.enrichments["status"] = AlertStatus.SUPPRESSED.value

    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Enriching alert",
        extra={
            "fingerprint": enrich_data.fingerprint,
            "tenant_id": tenant_id,
        },
    )

    return _enrich_alert(
        enrich_data,
        authenticated_entity=authenticated_entity,
        dispose_on_new_alert=dispose_on_new_alert,
        session=session,
    )


def _enrich_alert(
    enrich_data: EnrichAlertRequestBody,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:alert"])
    ),
    dispose_on_new_alert: Optional[bool] = False,
    session: Optional[Session] = None,
) -> dict[str, str]:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Enriching alert",
        extra={
            "fingerprint": enrich_data.fingerprint,
            "tenant_id": tenant_id,
        },
    )

    should_run_workflow = False
    should_check_incidents_resolution = False

    try:
        enrichement_bl = EnrichmentsBl(tenant_id, db=session)
        # Shahar: TODO, change to the specific action type, good enough for now
        if (
            "status" in enrich_data.enrichments
            and authenticated_entity.api_key_name is None
        ):
            action_type = (
                ActionType.MANUAL_RESOLVE
                if enrich_data.enrichments["status"] == "resolved"
                else ActionType.MANUAL_STATUS_CHANGE
            )
            action_description = f"Alert status was changed to {enrich_data.enrichments['status']} by {authenticated_entity.email}"
            should_run_workflow = True
            if enrich_data.enrichments["status"] == "resolved":
                should_check_incidents_resolution = True
        elif "status" in enrich_data.enrichments and authenticated_entity.api_key_name:
            action_type = (
                ActionType.API_AUTOMATIC_RESOLVE
                if enrich_data.enrichments["status"] == "resolved"
                else ActionType.API_STATUS_CHANGE
            )
            action_description = f"Alert status was changed to {enrich_data.enrichments['status']} by API `{authenticated_entity.api_key_name}`"
            should_run_workflow = True
            if enrich_data.enrichments["status"] == "resolved":
                should_check_incidents_resolution = True
        elif "note" in enrich_data.enrichments and enrich_data.enrichments["note"]:
            action_type = ActionType.COMMENT
            action_description = f"Comment added by {authenticated_entity.email} - {enrich_data.enrichments['note']}"
        elif "ticket_url" in enrich_data.enrichments:
            action_type = ActionType.TICKET_ASSIGNED
            action_description = f"Ticket assigned by {authenticated_entity.email} - {enrich_data.enrichments['ticket_url']}"
        else:
            action_type = ActionType.GENERIC_ENRICH
            action_description = f"Alert enriched by {authenticated_entity.email} - {enrich_data.enrichments}"

        enrichments = deepcopy(enrich_data.enrichments)
        enrichement_bl.enrich_entity(
            fingerprint=enrich_data.fingerprint,
            enrichments=enrichments,
            action_type=action_type,
            action_callee=authenticated_entity.email,
            action_description=action_description,
            dispose_on_new_alert=dispose_on_new_alert,
        )
        last_alert = get_last_alert_by_fingerprint(
            authenticated_entity.tenant_id, enrich_data.fingerprint, session=session
        )
        if dispose_on_new_alert:
            # Create instance-wide enrichment for history

            # For better database-native UUID support
            alert_id = UUIDType(binary=False).process_bind_param(
                last_alert.alert_id, session.bind.dialect
            )

            enrichement_bl.enrich_entity(
                fingerprint=alert_id,
                enrichments=enrich_data.enrichments,
                action_type=action_type,
                action_callee=authenticated_entity.email,
                action_description=action_description,
                audit_enabled=False,
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

        enriched_alerts_dto = convert_db_alerts_to_dto_alerts(alert, session=session)
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
        pusher_client = get_pusher_client()
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

        if should_run_workflow:
            workflow_manager = WorkflowManager.get_instance()
            workflow_manager.insert_events(
                tenant_id=tenant_id, events=[enriched_alerts_dto[0]]
            )

        # @tb add "and session" cuz I saw AttributeError: 'NoneType' object has no attribute 'add'"
        if should_check_incidents_resolution and session:
            enrich_alerts_with_incidents(tenant_id=tenant_id, alerts=alert)
            for incident in alert[0]._incidents:
                if (
                    incident.resolve_on == ResolveOn.ALL.value
                    and is_all_alerts_resolved(incident=incident, session=session)
                ):
                    incident.status = IncidentStatus.RESOLVED.value
                    session.add(incident)
                session.commit()

        return {"status": "ok"}

    except Exception as e:
        logger.exception("Failed to enrich alert", extra={"error": str(e)})
        return {"status": "failed"}


@router.post(
    "/unenrich",
    description="Un-Enrich an alert",
)
def unenrich_alert(
    enrich_data: UnEnrichAlertRequestBody,
    pusher_client: Pusher = Depends(get_pusher_client),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:alert"])
    ),
) -> dict[str, str]:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Un-Enriching alert",
        extra={
            "fingerprint": enrich_data.fingerprint,
            "tenant_id": tenant_id,
        },
    )

    if "assignees" in enrich_data.enrichments:
        return {"status": "failed"}

    alert = get_alerts_by_fingerprint(
        authenticated_entity.tenant_id, enrich_data.fingerprint, limit=1
    )
    if not alert:
        logger.warning(
            "Alert not found", extra={"fingerprint": enrich_data.fingerprint}
        )
        return {"status": "failed"}

    try:
        enrichement_bl = EnrichmentsBl(tenant_id)
        if "status" in enrich_data.enrichments:
            action_type = ActionType.STATUS_UNENRICH
            action_description = (
                f"Alert status was un-enriched by {authenticated_entity.email}"
            )
        elif "note" in enrich_data.enrichments:
            action_type = ActionType.UNCOMMENT
            action_description = f"Comment removed by {authenticated_entity.email}"
        elif "ticket_url" in enrich_data.enrichments:
            action_type = ActionType.TICKET_UNASSIGNED
            action_description = f"Ticket unassigned by {authenticated_entity.email}"
        else:
            action_type = ActionType.GENERIC_UNENRICH
            action_description = f"Alert en-enriched by {authenticated_entity.email}"

        enrichments_object = get_enrichment(tenant_id, enrich_data.fingerprint)
        enrichments = enrichments_object.enrichments

        new_enrichments = {
            key: value
            for key, value in enrichments.items()
            if key not in enrich_data.enrichments
        }

        enrichement_bl.enrich_entity(
            fingerprint=enrich_data.fingerprint,
            enrichments=new_enrichments,
            action_type=action_type,
            action_callee=authenticated_entity.email,
            action_description=action_description,
            force=True,
        )

        alert = get_alerts_by_fingerprint(
            authenticated_entity.tenant_id, enrich_data.fingerprint, limit=1
        )

        enriched_alerts_dto = convert_db_alerts_to_dto_alerts(alert)
        # push the enriched alert to the elasticsearch
        try:
            logger.info("Pushing enriched alert to elasticsearch")
            elastic_client = ElasticClient(tenant_id)
            elastic_client.index_alert(
                alert=enriched_alerts_dto[0],
            )
            logger.info("Pushed un-enriched alert to elasticsearch")
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
            "Alert un-enriched successfully",
            extra={"fingerprint": enrich_data.fingerprint, "tenant_id": tenant_id},
        )
        return {"status": "ok"}

    except Exception as e:
        logger.exception("Failed to un-enrich alert", extra={"error": str(e)})
        return {"status": "failed"}


@router.post(
    "/search",
    description="Search alerts",
)
async def search_alerts(
    search_request: SearchAlertsRequest,  # Use the model directly
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
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


@router.post(
    "/audit",
    description="Get alert timeline audit trail for multiple fingerprints",
)
def get_multiple_fingerprint_alert_audit(
    fingerprints: list[str],
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
) -> list[AlertAuditDto]:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching alert audit",
        extra={"fingerprints": fingerprints, "tenant_id": tenant_id},
    )
    alert_audit = get_alert_audit_db(tenant_id, fingerprints)

    if not alert_audit:
        raise HTTPException(status_code=404, detail="Alert not found")
    grouped_events = []

    # Group the results by fingerprint for "deduplication" (2x, 3x, etc.) thingy..
    grouped_audit = {}
    for audit in alert_audit:
        if audit.fingerprint not in grouped_audit:
            grouped_audit[audit.fingerprint] = []
        grouped_audit[audit.fingerprint].append(audit)

    for values in grouped_audit.values():
        grouped_events.extend(AlertAuditDto.from_orm_list(values))
    return grouped_events


@router.get(
    "/{fingerprint}/audit",
    description="Get alert timeline audit trail",
)
def get_alert_audit(
    fingerprint: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
) -> list[AlertAuditDto]:
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

    grouped_events = AlertAuditDto.from_orm_list(alert_audit)
    return grouped_events


@router.get("/quality/metrics", description="Get alert quality")
def get_alert_quality(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
    time_stamp: TimeStampFilter = Depends(get_time_stamp_filter),
    fields: Optional[List[str]] = Query([]),
):
    logger.info(
        "Fetching alert quality metrics per provider",
        extra={"tenant_id": authenticated_entity.tenant_id, "fields": fields},
    )
    start_date = time_stamp.lower_timestamp if time_stamp else None
    end_date = time_stamp.upper_timestamp if time_stamp else None
    db_alerts_quality = get_alerts_metrics_by_provider(
        tenant_id=authenticated_entity.tenant_id,
        start_date=start_date,
        end_date=end_date,
        fields=fields,
    )

    return db_alerts_quality


@router.get(
    "/event/error",
    description="Get alerts that Keep failed to process",
)
def get_error_alerts(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
    limit: int = 1000,
) -> list[AlertErrorDto]:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching error alerts from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )
    error_alerts = get_error_alerts_db(tenant_id=tenant_id, limit=limit)
    error_alerts_dtos = [
        AlertErrorDto(
            id=str(alert.id),
            event=alert.raw_alert,
            error_message=alert.error_message,
            timestamp=alert.timestamp,
            provider_type=alert.provider_type,
        )
        for alert in error_alerts
    ]
    logger.info(
        "Fetched error alerts from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return error_alerts_dtos


@router.post(
    "/event/error/dismiss",
    description="Dismiss error alerts. If alert_id is provided, dismisses that specific alert. If no alert_id is provided, dismisses all alerts.",
)
def dismiss_error_alerts(
    request: DismissAlertRequest = None,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:alert"])
    ),
) -> dict:
    tenant_id = authenticated_entity.tenant_id

    # If alert_id is provided, dismiss a specific alert
    if request and request.alert_id:
        alert_id = request.alert_id

        logger.info(
            "Dismissing specific error alert",
            extra={
                "tenant_id": tenant_id,
                "alert_id": alert_id,
            },
        )

        # Update the alert in the database to mark it as dismissed
        dismiss_error_alerts_db(
            tenant_id=tenant_id,
            alert_id=alert_id,
            dismissed_by=authenticated_entity.email,
        )

        logger.info(
            "Successfully dismissed error alert",
            extra={
                "tenant_id": tenant_id,
                "alert_id": alert_id,
            },
        )

        return {"success": True, "message": "Alert dismissed successfully"}

    # If no alert_id is provided, dismiss all alerts
    else:
        logger.info(
            "Dismissing all error alerts for tenant",
            extra={
                "tenant_id": tenant_id,
            },
        )

        # Update all alerts for the tenant to mark them as dismissed
        dismiss_error_alerts_db(
            tenant_id=tenant_id, dismissed_by=authenticated_entity.email
        )

        logger.info(
            "Successfully dismissed all error alerts",
            extra={
                "tenant_id": tenant_id,
            },
        )

        return {"success": True, "message": "Successfully dismissed all alerts"}
