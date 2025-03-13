# builtins
import copy
import datetime
import json
import logging
import os
import sys
import time
import traceback
from typing import List

# third-parties
import dateutil
from arq import Retry
from fastapi.datastructures import FormData
from opentelemetry import trace
from sqlmodel import Session

# internals
from keep.api.alert_deduplicator.alert_deduplicator import AlertDeduplicator
from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.bl.incidents_bl import IncidentBl
from keep.api.bl.maintenance_windows_bl import MaintenanceWindowsBl
from keep.api.core.db import (
    bulk_upsert_alert_fields,
    enrich_alerts_with_incidents,
    get_alerts_by_fingerprint,
    get_all_presets_dtos,
    get_enrichment_with_session,
    get_last_alert_hashes_by_fingerprints,
    get_session_sync,
    set_last_alert,
)
from keep.api.core.dependencies import get_pusher_client
from keep.api.core.elastic import ElasticClient
from keep.api.core.metrics import (
    events_error_counter,
    events_in_counter,
    events_out_counter,
    processing_time_summary,
)
from keep.api.models.action_type import ActionType
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.alert import Alert, AlertAudit, AlertRaw
from keep.api.models.incident import IncidentDto
from keep.api.tasks.notification_cache import get_notification_cache
from keep.api.utils.enrichment_helpers import (
    calculated_start_firing_time,
    convert_db_alerts_to_dto_alerts,
)
from keep.providers.providers_factory import ProvidersFactory
from keep.rulesengine.rulesengine import RulesEngine
from keep.workflowmanager.workflowmanager import WorkflowManager

TIMES_TO_RETRY_JOB = 5  # the number of times to retry the job in case of failure
# Opt-outs/ins
KEEP_STORE_RAW_ALERTS = os.environ.get("KEEP_STORE_RAW_ALERTS", "false") == "true"
KEEP_CORRELATION_ENABLED = os.environ.get("KEEP_CORRELATION_ENABLED", "true") == "true"
KEEP_ALERT_FIELDS_ENABLED = (
    os.environ.get("KEEP_ALERT_FIELDS_ENABLED", "true") == "true"
)
KEEP_MAINTENANCE_WINDOWS_ENABLED = (
    os.environ.get("KEEP_MAINTENANCE_WINDOWS_ENABLED", "true") == "true"
)
KEEP_AUDIT_EVENTS_ENABLED = (
    os.environ.get("KEEP_AUDIT_EVENTS_ENABLED", "true") == "true"
)
KEEP_CALCULATE_START_FIRING_TIME_ENABLED = (
    os.environ.get("KEEP_CALCULATE_START_FIRING_TIME_ENABLED", "true") == "true"
)

logger = logging.getLogger(__name__)


def __internal_prepartion(
    alerts: list[AlertDto], fingerprint: str | None, api_key_name: str | None
):
    """
    Internal function to prepare the alerts for the digest

    Args:
        alerts (list[AlertDto]): List of alerts to iterate over
        fingerprint (str | None): Fingerprint to set on the alerts
        api_key_name (str | None): API key name to set on the alerts (that were used to push them)
    """
    for alert in alerts:
        try:
            if not alert.source:
                alert.source = ["keep"]
        # weird bug on Mailgun where source is int
        except Exception:
            logger.exception(
                "failed to parse source",
                extra={
                    "alert": alerts,
                },
            )
            raise

        if fingerprint is not None:
            alert.fingerprint = fingerprint

        if api_key_name is not None:
            alert.apiKeyRef = api_key_name


def __save_to_db(
    tenant_id,
    provider_type,
    session: Session,
    raw_events: list[dict],
    formatted_events: list[AlertDto],
    deduplicated_events: list[AlertDto],
    provider_id: str | None = None,
    timestamp_forced: datetime.datetime | None = None,
):
    try:
        # keep raw events in the DB if the user wants to
        # this is mainly for debugging and research purposes
        if KEEP_STORE_RAW_ALERTS:
            if isinstance(raw_events, dict):
                raw_events = [raw_events]

            for raw_event in raw_events:
                alert = AlertRaw(
                    tenant_id=tenant_id,
                    raw_alert=raw_event,
                    provider_type=provider_type,
                )
                session.add(alert)

        # add audit to the deduplicated events
        # TODO: move this to the alert deduplicator
        if KEEP_AUDIT_EVENTS_ENABLED:
            for event in deduplicated_events:
                audit = AlertAudit(
                    tenant_id=tenant_id,
                    fingerprint=event.fingerprint,
                    status=event.status,
                    action=ActionType.DEDUPLICATED.value,
                    user_id="system",
                    description="Alert was deduplicated",
                )
                session.add(audit)

        enriched_formatted_events = []
        saved_alerts = []

        for formatted_event in formatted_events:
            formatted_event.pushed = True

            if KEEP_CALCULATE_START_FIRING_TIME_ENABLED:
                # calculate startFiring time
                previous_alert = get_alerts_by_fingerprint(
                    tenant_id=tenant_id,
                    fingerprint=formatted_event.fingerprint,
                    limit=1,
                )
                previous_alert = convert_db_alerts_to_dto_alerts(previous_alert)
                formatted_event.firingStartTime = calculated_start_firing_time(
                    formatted_event, previous_alert
                )

            enrichments_bl = EnrichmentsBl(tenant_id, session)
            # Dispose enrichments that needs to be disposed
            try:
                enrichments_bl.dispose_enrichments(formatted_event.fingerprint)
            except Exception:
                logger.exception(
                    "Failed to dispose enrichments",
                    extra={
                        "tenant_id": tenant_id,
                        "fingerprint": formatted_event.fingerprint,
                    },
                )

            # Post format enrichment
            try:
                formatted_event = enrichments_bl.run_extraction_rules(formatted_event)
            except Exception:
                logger.exception(
                    "Failed to run post-formatting extraction rules",
                    extra={
                        "tenant_id": tenant_id,
                        "fingerprint": formatted_event.fingerprint,
                    },
                )

            # Make sure the lastReceived is a valid date string
            # tb: we do this because `AlertDto` object lastReceived is a string and not a datetime object
            # TODO: `AlertDto` object `lastReceived` should be a datetime object so we can easily validate with pydantic
            if not formatted_event.lastReceived:
                formatted_event.lastReceived = datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat()
            else:
                try:
                    dateutil.parser.isoparse(formatted_event.lastReceived)
                except ValueError:
                    logger.warning("Invalid lastReceived date, setting to now")
                    formatted_event.lastReceived = datetime.datetime.now(
                        tz=datetime.timezone.utc
                    ).isoformat()

            alert_args = {
                "tenant_id": tenant_id,
                "provider_type": (
                    provider_type if provider_type else formatted_event.source[0]
                ),
                "event": formatted_event.dict(),
                "provider_id": provider_id,
                "fingerprint": formatted_event.fingerprint,
                "alert_hash": formatted_event.alert_hash,
            }
            if timestamp_forced is not None:
                alert_args["timestamp"] = timestamp_forced

            alert = Alert(**alert_args)
            session.add(alert)
            session.flush()
            saved_alerts.append(alert)
            alert_id = alert.id
            formatted_event.event_id = str(alert_id)

            if KEEP_AUDIT_EVENTS_ENABLED:
                audit = AlertAudit(
                    tenant_id=tenant_id,
                    fingerprint=formatted_event.fingerprint,
                    action=(
                        ActionType.AUTOMATIC_RESOLVE.value
                        if formatted_event.status == AlertStatus.RESOLVED.value
                        else ActionType.TIGGERED.value
                    ),
                    user_id="system",
                    description=f"Alert recieved from provider with status {formatted_event.status}",
                )
                session.add(audit)

            session.commit()
            session.flush()
            set_last_alert(tenant_id, alert, session=session)

            # Mapping
            try:
                enrichments_bl.run_mapping_rules(formatted_event)
            except Exception:
                logger.exception("Failed to run mapping rules")

            alert_enrichment = get_enrichment_with_session(
                session=session,
                tenant_id=tenant_id,
                fingerprint=formatted_event.fingerprint,
            )
            if alert_enrichment:
                for enrichment in alert_enrichment.enrichments:
                    # set the enrichment
                    value = alert_enrichment.enrichments[enrichment]
                    if isinstance(value, str):
                        value = value.strip()
                    setattr(formatted_event, enrichment, value)
            enriched_formatted_events.append(formatted_event)

        logger.info("Checking for incidents to resolve", extra={"tenant_id": tenant_id})
        try:
            saved_alerts = enrich_alerts_with_incidents(
                tenant_id, saved_alerts, session
            )  # note: this only enriches incidents that were not yet ended
            for alert in saved_alerts:
                if alert.event.get("status") == AlertStatus.RESOLVED.value:
                    logger.debug(
                        "Checking for alert with status resolved",
                        extra={"alert_id": alert.id, "tenant_id": tenant_id},
                    )
                    for incident in alert._incidents:
                        IncidentBl(tenant_id, session).resolve_incident_if_require(
                            incident
                        )
            logger.info(
                "Completed checking for incidents to resolve",
                extra={"tenant_id": tenant_id},
            )
        except Exception:
            logger.exception(
                "Failed to check for incidents to resolve",
                extra={"tenant_id": tenant_id},
            )
        session.commit()

        logger.info(
            "Added new alerts to the DB",
            extra={
                "provider_type": provider_type,
                "num_of_alerts": len(formatted_events),
                "provider_id": provider_id,
                "tenant_id": tenant_id,
            },
        )
        return enriched_formatted_events
    except Exception:
        logger.exception(
            "Failed to add new alerts to the DB",
            extra={
                "provider_type": provider_type,
                "num_of_alerts": len(formatted_events),
                "provider_id": provider_id,
                "tenant_id": tenant_id,
            },
        )
        raise


def __handle_formatted_events(
    tenant_id,
    provider_type,
    session: Session,
    raw_events: list[dict],
    formatted_events: list[AlertDto],
    tracer: trace.Tracer,
    provider_id: str | None = None,
    notify_client: bool = True,
    timestamp_forced: datetime.datetime | None = None,
    job_id: str | None = None,
):
    """
    this is super important function and does five things:
    0. checks for deduplications using alertdeduplicator
    1. adds the alerts to the DB
    2. adds the alerts to elasticsearch
    3. runs workflows based on the alerts
    4. runs the rules engine
    5. update the presets

    TODO: add appropriate logs, trace and all of that so we can track errors

    """
    logger.info(
        "Adding new alerts to the DB",
        extra={
            "provider_type": provider_type,
            "num_of_alerts": len(formatted_events),
            "provider_id": provider_id,
            "tenant_id": tenant_id,
            "job_id": job_id,
        },
    )

    # first, check for maintenance windows
    if KEEP_MAINTENANCE_WINDOWS_ENABLED:
        with tracer.start_as_current_span("process_event_maintenance_windows_check"):
            maintenance_windows_bl = MaintenanceWindowsBl(
                tenant_id=tenant_id, session=session
            )
            if maintenance_windows_bl.maintenance_rules:
                formatted_events = [
                    event
                    for event in formatted_events
                    if maintenance_windows_bl.check_if_alert_in_maintenance_windows(
                        event
                    )
                    is False
                ]
            else:
                logger.debug(
                    "No maintenance windows configured for this tenant",
                    extra={"tenant_id": tenant_id},
                )

            if not formatted_events:
                logger.info(
                    "No alerts to process after running maintenance windows check",
                    extra={"tenant_id": tenant_id},
                )
                return

    with tracer.start_as_current_span("process_event_deduplication"):
        # second, filter out any deduplicated events
        alert_deduplicator = AlertDeduplicator(tenant_id)
        deduplication_rules = alert_deduplicator.get_deduplication_rules(
            tenant_id=tenant_id, provider_id=provider_id, provider_type=provider_type
        )
        last_alerts_fingerprint_to_hash = get_last_alert_hashes_by_fingerprints(
            tenant_id, [event.fingerprint for event in formatted_events]
        )
        for event in formatted_events:
            # apply_deduplication set alert_hash and isDuplicate on event
            event = alert_deduplicator.apply_deduplication(
                event, deduplication_rules, last_alerts_fingerprint_to_hash
            )

        # filter out the deduplicated events
        deduplicated_events = list(
            filter(lambda event: event.isFullDuplicate, formatted_events)
        )
        formatted_events = list(
            filter(lambda event: not event.isFullDuplicate, formatted_events)
        )

    with tracer.start_as_current_span("process_event_save_to_db"):
        # save to db
        enriched_formatted_events = __save_to_db(
            tenant_id,
            provider_type,
            session,
            raw_events,
            formatted_events,
            deduplicated_events,
            provider_id,
            timestamp_forced,
        )

    # let's save all fields to the DB so that we can use them in the future such in deduplication fields suggestions
    # todo: also use it on correlation rules suggestions
    if KEEP_ALERT_FIELDS_ENABLED:
        with tracer.start_as_current_span("process_event_bulk_upsert_alert_fields"):
            for enriched_formatted_event in enriched_formatted_events:
                logger.debug(
                    "Bulk upserting alert fields",
                    extra={
                        "alert_event_id": enriched_formatted_event.event_id,
                        "alert_fingerprint": enriched_formatted_event.fingerprint,
                    },
                )
                fields = []
                for key, value in enriched_formatted_event.dict().items():
                    if isinstance(value, dict):
                        for nested_key in value.keys():
                            fields.append(f"{key}.{nested_key}")
                    else:
                        fields.append(key)

                bulk_upsert_alert_fields(
                    tenant_id=tenant_id,
                    fields=fields,
                    provider_id=enriched_formatted_event.providerId,
                    provider_type=enriched_formatted_event.providerType,
                    session=session,
                )

                logger.debug(
                    "Bulk upserted alert fields",
                    extra={
                        "alert_event_id": enriched_formatted_event.event_id,
                        "alert_fingerprint": enriched_formatted_event.fingerprint,
                    },
                )

    # after the alert enriched and mapped, lets send it to the elasticsearch
    with tracer.start_as_current_span("process_event_push_to_elasticsearch"):
        elastic_client = ElasticClient(tenant_id=tenant_id)
        if elastic_client.enabled:
            for alert in enriched_formatted_events:
                try:
                    logger.debug(
                        "Pushing alert to elasticsearch",
                        extra={
                            "alert_event_id": alert.event_id,
                            "alert_fingerprint": alert.fingerprint,
                        },
                    )
                    elastic_client.index_alert(
                        alert=alert,
                    )
                except Exception:
                    logger.exception(
                        "Failed to push alerts to elasticsearch",
                        extra={
                            "provider_type": provider_type,
                            "num_of_alerts": len(formatted_events),
                            "provider_id": provider_id,
                            "tenant_id": tenant_id,
                        },
                    )
                    continue

    with tracer.start_as_current_span("process_event_push_to_workflows"):
        try:
            # Now run any workflow that should run based on this alert
            # TODO: this should publish event
            workflow_manager = WorkflowManager.get_instance()
            # insert the events to the workflow manager process queue
            logger.info("Adding events to the workflow manager queue")
            workflow_manager.insert_events(tenant_id, enriched_formatted_events)
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

    incidents = []
    with tracer.start_as_current_span("process_event_run_rules_engine"):
        # Now we need to run the rules engine
        if KEEP_CORRELATION_ENABLED:
            try:
                rules_engine = RulesEngine(tenant_id=tenant_id)
                # handle incidents, also handle workflow execution as
                incidents: List[IncidentDto] = rules_engine.run_rules(
                    enriched_formatted_events, session=session
                )
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

    with tracer.start_as_current_span("process_event_notify_client"):
        pusher_client = get_pusher_client() if notify_client else None
        if not pusher_client:
            return
        # Get the notification cache
        pusher_cache = get_notification_cache()

        # Tell the client to poll alerts
        if pusher_cache.should_notify(tenant_id, "poll-alerts"):
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

        if incidents and pusher_cache.should_notify(tenant_id, "incident-change"):
            try:
                pusher_client.trigger(
                    f"private-{tenant_id}",
                    "incident-change",
                    {},
                )
            except Exception:
                logger.exception("Failed to tell the client to pull incidents")

        # Now we need to update the presets
        # send with pusher

        try:
            presets = get_all_presets_dtos(tenant_id)
            rules_engine = RulesEngine(tenant_id=tenant_id)
            presets_do_update = []
            for preset_dto in presets:
                # filter the alerts based on the search query
                filtered_alerts = rules_engine.filter_alerts(
                    enriched_formatted_events, preset_dto.cel_query
                )
                # if not related alerts, no need to update
                if not filtered_alerts:
                    continue
                presets_do_update.append(preset_dto)
            if pusher_cache.should_notify(tenant_id, "poll-presets"):
                try:
                    pusher_client.trigger(
                        f"private-{tenant_id}",
                        "poll-presets",
                        json.dumps(
                            [p.name.lower() for p in presets_do_update], default=str
                        ),
                    )
                except Exception:
                    logger.exception("Failed to send presets via pusher")
        except Exception:
            logger.exception(
                "Failed to send presets via pusher",
                extra={
                    "provider_type": provider_type,
                    "num_of_alerts": len(formatted_events),
                    "provider_id": provider_id,
                    "tenant_id": tenant_id,
                },
            )
    return enriched_formatted_events


@processing_time_summary.time()
def process_event(
    ctx: dict,  # arq context
    tenant_id: str,
    provider_type: str | None,
    provider_id: str | None,
    fingerprint: str | None,
    api_key_name: str | None,
    trace_id: str | None,  # so we can track the job from the request to the digest
    event: (
        AlertDto | list[AlertDto] | IncidentDto | list[IncidentDto] | dict | None
    ),  # the event to process, either plain (generic) or from a specific provider
    notify_client: bool = True,
    timestamp_forced: datetime.datetime | None = None,
) -> list[Alert]:
    start_time = time.time()
    job_id = ctx.get("job_id")

    extra_dict = {
        "tenant_id": tenant_id,
        "provider_type": provider_type,
        "provider_id": provider_id,
        "fingerprint": fingerprint,
        "event_type": str(type(event)),
        "trace_id": trace_id,
        "job_id": job_id,
        "raw_event": (
            event if KEEP_STORE_RAW_ALERTS else None
        ),  # Let's log the events if we store it for debugging
    }
    logger.info("Processing event", extra=extra_dict)

    tracer = trace.get_tracer(__name__)

    raw_event = copy.deepcopy(event)
    events_in_counter.inc()
    try:
        with tracer.start_as_current_span("process_event_get_db_session"):
            # Create a session to be used across the processing task
            session = get_session_sync()

        # Pre alert formatting extraction rules
        with tracer.start_as_current_span("process_event_pre_alert_formatting"):
            enrichments_bl = EnrichmentsBl(tenant_id, session)
            try:
                event = enrichments_bl.run_extraction_rules(event, pre=True)
            except Exception:
                logger.exception("Failed to run pre-formatting extraction rules")

        with tracer.start_as_current_span("process_event_provider_formatting"):
            if (
                provider_type is not None
                and isinstance(event, dict)
                or isinstance(event, FormData)
                or isinstance(event, list)
            ):
                try:
                    provider_class = ProvidersFactory.get_provider_class(provider_type)
                except Exception:
                    provider_class = ProvidersFactory.get_provider_class("keep")

                if isinstance(event, list):
                    event_list = []
                    for event_item in event:
                        if not isinstance(event_item, AlertDto):
                            event_list.append(
                                provider_class.format_alert(
                                    tenant_id=tenant_id,
                                    event=event_item,
                                    provider_id=provider_id,
                                    provider_type=provider_type,
                                )
                            )
                        else:
                            event_list.append(event_item)
                    event = event_list
                else:
                    event = provider_class.format_alert(
                        tenant_id=tenant_id,
                        event=event,
                        provider_id=provider_id,
                        provider_type=provider_type,
                    )
                # SHAHAR: for aws cloudwatch, we get a subscription notification message that we should skip
                #         todo: move it to be generic
                if event is None and provider_type == "cloudwatch":
                    logger.info(
                        "This is a subscription notification message from AWS - skipping processing"
                    )
                    return
                elif event is None:
                    logger.info(
                        "Provider returned None (failed silently), skipping processing"
                    )

        if event:
            if isinstance(event, str):
                extra_dict["raw_event"] = event
                logger.error(
                    "Event is a string (malformed json?), skipping processing",
                    extra=extra_dict,
                )
                return None

            # In case when provider_type is not set
            if isinstance(event, dict):
                if not event.get("name"):
                    event["name"] = event.get("id", "unknown alert name")
                event = [AlertDto(**event)]
                raw_event = [raw_event]

            # Prepare the event for the digest
            if isinstance(event, AlertDto):
                event = [event]
                raw_event = [raw_event]

            with tracer.start_as_current_span("process_event_internal_preparation"):
                __internal_prepartion(event, fingerprint, api_key_name)

            formatted_events = __handle_formatted_events(
                tenant_id,
                provider_type,
                session,
                raw_event,
                event,
                tracer,
                provider_id,
                notify_client,
                timestamp_forced,
                job_id,
            )

            logger.info(
                "Event processed",
                extra={**extra_dict, "processing_time": time.time() - start_time},
            )
            events_out_counter.inc()
            return formatted_events
    except Exception:
        stacktrace = traceback.format_exc()
        tb = traceback.extract_tb(sys.exc_info()[2])

        # Get the name of the last function in the traceback
        try:
            last_function = tb[-1].name if tb else ""
        except Exception:
            last_function = ""

        # Check if the last function matches the pattern
        if "_format_alert" in last_function or "_format" in last_function:
            logger.exception(
                "Error processing event",
                extra={**extra_dict, "processing_time": time.time() - start_time},
            )
            # In case of exception, add the alerts to the defect table
            error_msg = stacktrace
        # if this is a bug in the code, we don't want the user to see the stacktrace
        else:
            error_msg = "Error processing event, contact Keep team for more information"

        __save_error_alerts(tenant_id, provider_type, raw_event, error_msg)
        events_error_counter.inc()

        # Retrying only if context is present (running the job in arq worker)
        if bool(ctx):
            raise Retry(defer=ctx["job_try"] * TIMES_TO_RETRY_JOB)
    finally:
        session.close()


def __save_error_alerts(
    tenant_id,
    provider_type,
    raw_events: dict | list[dict] | list[AlertDto] | None,
    error_message: str,
):
    if not raw_events:
        logger.info("No raw events to save as errors")
        return

    try:
        logger.info(
            "Getting database session",
            extra={
                "tenant_id": tenant_id,
            },
        )
        session = get_session_sync()

        # Convert to list if single dict
        if isinstance(raw_events, dict):
            logger.info("Converting single dict to list")
            raw_events = [raw_events]

        logger.info(f"Saving {len(raw_events)} error alerts")

        if len(raw_events) > 5:
            logger.info(
                "Raw Alert Payload",
                extra={
                    "tenant_id": tenant_id,
                    "raw_events": raw_events,
                },
            )
        for raw_event in raw_events:
            # Convert AlertDto to dict if needed
            if isinstance(raw_event, AlertDto):
                logger.info("Converting AlertDto to dict")
                raw_event = raw_event.dict()

            # TODO: change to debug
            logger.debug(
                "Creating AlertRaw object",
                extra={
                    "tenant_id": tenant_id,
                    "raw_event": raw_event,
                },
            )
            alert = AlertRaw(
                tenant_id=tenant_id,
                raw_alert=raw_event,
                provider_type=provider_type,
                error=True,
                error_message=error_message,
            )
            session.add(alert)
            logger.info("AlertRaw object created")
        session.commit()
        logger.info("Successfully saved error alerts")
    except Exception:
        logger.exception("Failed to save error alerts")
    finally:
        session.close()


async def async_process_event(*args, **kwargs):
    return process_event(*args, **kwargs)
