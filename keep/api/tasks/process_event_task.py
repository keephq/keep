# builtins
import copy
import datetime
import json
import logging
import os
from typing import List

import dateutil

# third-parties
from arq import Retry
from fastapi.datastructures import FormData
from sqlmodel import Session

# internals
from keep.api.alert_deduplicator.alert_deduplicator import AlertDeduplicator
from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.bl.maintenance_windows_bl import MaintenanceWindowsBl
from keep.api.core.db import (
    bulk_upsert_alert_fields,
    get_alerts_by_fingerprint,
    get_all_presets,
    get_enrichment_with_session,
    get_session_sync,
)
from keep.api.core.dependencies import get_pusher_client
from keep.api.core.elastic import ElasticClient
from keep.api.models.alert import AlertDto, AlertStatus, IncidentDto
from keep.api.models.db.alert import Alert, AlertActionType, AlertAudit, AlertRaw
from keep.api.models.db.preset import PresetDto
from keep.api.utils.enrichment_helpers import (
    calculated_start_firing_time,
    convert_db_alerts_to_dto_alerts,
)
from keep.providers.providers_factory import ProvidersFactory
from keep.rulesengine.rulesengine import RulesEngine
from keep.workflowmanager.workflowmanager import WorkflowManager

TIMES_TO_RETRY_JOB = 5  # the number of times to retry the job in case of failure
KEEP_STORE_RAW_ALERTS = os.environ.get("KEEP_STORE_RAW_ALERTS", "false") == "true"

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
        if not alert.source:
            alert.source = ["keep"]

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
            for raw_event in raw_events:
                alert = AlertRaw(
                    tenant_id=tenant_id,
                    raw_alert=raw_event,
                )
                session.add(alert)
        # add audit to the deduplicated events
        for event in deduplicated_events:
            audit = AlertAudit(
                tenant_id=tenant_id,
                fingerprint=event.fingerprint,
                status=event.status,
                action=AlertActionType.DEDUPLICATED.value,
                user_id="system",
                description="Alert was deduplicated",
            )
            session.add(audit)
        enriched_formatted_events = []
        for formatted_event in formatted_events:
            formatted_event.pushed = True
            # calculate startFiring time
            previous_alert = get_alerts_by_fingerprint(
                tenant_id=tenant_id, fingerprint=formatted_event.fingerprint, limit=1
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
            alert_id = alert.id
            formatted_event.event_id = str(alert_id)
            audit = AlertAudit(
                tenant_id=tenant_id,
                fingerprint=formatted_event.fingerprint,
                action=(
                    AlertActionType.AUTOMATIC_RESOLVE.value
                    if formatted_event.status == AlertStatus.RESOLVED.value
                    else AlertActionType.TIGGERED.value
                ),
                user_id="system",
                description=f"Alert recieved from provider with status {formatted_event.status}",
            )
            session.add(audit)
            alert_dto = AlertDto(**formatted_event.dict())
            # Mapping
            try:
                enrichments_bl.run_mapping_rules(alert_dto)
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
                    setattr(alert_dto, enrichment, value)
            enriched_formatted_events.append(alert_dto)
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
        return enriched_formatted_events
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
        raise


def __handle_formatted_events(
    tenant_id,
    provider_type,
    session: Session,
    raw_events: list[dict],
    formatted_events: list[AlertDto],
    provider_id: str | None = None,
    notify_client: bool = True,
    timestamp_forced: datetime.datetime | None = None,
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
        "Asyncronusly adding new alerts to the DB",
        extra={
            "provider_type": provider_type,
            "num_of_alerts": len(formatted_events),
            "provider_id": provider_id,
            "tenant_id": tenant_id,
        },
    )

    # first, check for maintenance windows
    maintenance_windows_bl = MaintenanceWindowsBl(tenant_id=tenant_id, session=session)
    if maintenance_windows_bl.maintenance_rules:
        formatted_events = [
            event
            for event in formatted_events
            if maintenance_windows_bl.check_if_alert_in_maintenance_windows(event)
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

    # second, filter out any deduplicated events
    alert_deduplicator = AlertDeduplicator(tenant_id)

    for event in formatted_events:
        # apply deduplication
        # apply_deduplication set alert_hash and isDuplicate on event
        event = alert_deduplicator.apply_deduplication(event)

    # filter out the deduplicated events
    deduplicated_events = list(
        filter(lambda event: event.isFullDuplicate, formatted_events)
    )
    formatted_events = list(
        filter(lambda event: not event.isFullDuplicate, formatted_events)
    )

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
    elastic_client = ElasticClient(tenant_id=tenant_id)
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
    # Now we need to run the rules engine
    try:
        rules_engine = RulesEngine(tenant_id=tenant_id)
        incidents: List[IncidentDto] = rules_engine.run_rules(
            enriched_formatted_events, session=session
        )

        # TODO: Replace with incidents workflow triggers. Ticket: https://github.com/keephq/keep/issues/1527
        # if new grouped incidents were created, we need to push them to the client
        # if incidents:
        #     logger.info("Adding group alerts to the workflow manager queue")
        #     workflow_manager.insert_events(tenant_id, grouped_alerts)
        #     logger.info("Added group alerts to the workflow manager queue")
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

    # Tell the client to poll alerts
    if notify_client and incidents:
        pusher_client = get_pusher_client()
        if not pusher_client:
            return
        try:
            pusher_client.trigger(
                f"private-{tenant_id}",
                "incident-change",
                {},
            )
        except Exception:
            logger.exception("Failed to push alert to the client")

    # Now we need to update the presets
    # send with pusher
    if notify_client:
        pusher_client = get_pusher_client()
        if not pusher_client:
            return
    try:
        presets = get_all_presets(tenant_id)
        rules_engine = RulesEngine(tenant_id=tenant_id)
        presets_do_update = []
        for preset in presets:
            # filter the alerts based on the search query
            preset_dto = PresetDto(**preset.to_dict())
            filtered_alerts = rules_engine.filter_alerts(
                enriched_formatted_events, preset_dto.cel_query
            )
            # if not related alerts, no need to update
            if not filtered_alerts:
                continue
            presets_do_update.append(preset_dto)
            preset_dto.alerts_count = len(filtered_alerts)
            # update noisy
            if preset.is_noisy:
                firing_filtered_alerts = list(
                    filter(
                        lambda alert: alert.status == AlertStatus.FIRING.value,
                        filtered_alerts,
                    )
                )
                # if there are firing alerts, then do noise
                if firing_filtered_alerts:
                    logger.info("Noisy preset is noisy")
                    preset_dto.should_do_noise_now = True
            # else if at least one of the alerts has isNoisy and should fire:
            elif any(
                alert.isNoisy and alert.status == AlertStatus.FIRING.value
                for alert in filtered_alerts
                if hasattr(alert, "isNoisy")
            ):
                logger.info("Noisy preset is noisy")
                preset_dto.should_do_noise_now = True
            try:
                pusher_client.trigger(
                    f"private-{tenant_id}",
                    "async-presets",
                    json.dumps([p.dict() for p in presets_do_update], default=str),
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


def process_event(
    ctx: dict,  # arq context
    tenant_id: str,
    provider_type: str | None,
    provider_id: str | None,
    fingerprint: str | None,
    api_key_name: str | None,
    trace_id: str | None,  # so we can track the job from the request to the digest
    event: (
        AlertDto | list[AlertDto] | dict
    ),  # the event to process, either plain (generic) or from a specific provider
    notify_client: bool = True,
    timestamp_forced: datetime.datetime | None = None,
):
    extra_dict = {
        "tenant_id": tenant_id,
        "provider_type": provider_type,
        "provider_id": provider_id,
        "fingerprint": fingerprint,
        "event_type": str(type(event)),
        "trace_id": trace_id,
        "job_id": ctx.get("job_id"),
        "raw_event": (
            event if KEEP_STORE_RAW_ALERTS else None
        ),  # Let's log the events if we store it for debugging
    }
    logger.info("Processing event", extra=extra_dict)
    raw_event = copy.deepcopy(event)
    try:
        session = get_session_sync()
        # Pre alert formatting extraction rules
        enrichments_bl = EnrichmentsBl(tenant_id, session)
        try:
            event = enrichments_bl.run_extraction_rules(event, pre=True)
        except Exception:
            logger.exception("Failed to run pre-formatting extraction rules")

        if (
            provider_type is not None
            and isinstance(event, dict)
            or isinstance(event, FormData)
        ):
            provider_class = ProvidersFactory.get_provider_class(provider_type)
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

        # In case when provider_type is not set
        if isinstance(event, dict):
            event = [AlertDto(**event)]
            raw_event = [raw_event]

        # Prepare the event for the digest
        if isinstance(event, AlertDto):
            event = [event]
            raw_event = [raw_event]

        __internal_prepartion(event, fingerprint, api_key_name)
        __handle_formatted_events(
            tenant_id,
            provider_type,
            session,
            raw_event,
            event,
            provider_id,
            notify_client,
            timestamp_forced,
        )
    except Exception:
        logger.exception("Error processing event", extra=extra_dict)
        # Retrying only if context is present (running the job in arq worker)
        if bool(ctx):
            raise Retry(defer=ctx["job_try"] * TIMES_TO_RETRY_JOB)
    finally:
        session.close()
    logger.info("Event processed", extra=extra_dict)


async def async_process_event(*args, **kwargs):
    return process_event(*args, **kwargs)
