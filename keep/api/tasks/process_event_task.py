# builtins
import copy
import datetime
import json
import logging
import os

import dateutil

# third-parties
from arq import Retry
from sqlmodel import Session

# internals
from keep.api.alert_deduplicator.alert_deduplicator import AlertDeduplicator
from keep.api.bl.enrichments import EnrichmentsBl
from keep.api.core.db import get_all_presets, get_enrichment, get_session_sync
from keep.api.core.dependencies import get_pusher_client
from keep.api.core.elastic import ElasticClient
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.alert import Alert, AlertActionType, AlertAudit, AlertRaw
from keep.api.models.db.preset import PresetDto
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

            enrichments_bl = EnrichmentsBl(tenant_id, session)
            # Dispose enrichments that needs to be disposed
            try:
                enrichments_bl.dispose_enrichments(formatted_event.fingerprint)
            except Exception:
                logger.exception("Failed to dispose enrichments")

            # Post format enrichment
            try:
                formatted_event = enrichments_bl.run_extraction_rules(formatted_event)
            except Exception:
                logger.exception("Failed to run post-formatting extraction rules")

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

            alert = Alert(
                tenant_id=tenant_id,
                provider_type=(
                    provider_type if provider_type else formatted_event.source[0]
                ),
                event=formatted_event.dict(),
                provider_id=provider_id,
                fingerprint=formatted_event.fingerprint,
                alert_hash=formatted_event.alert_hash,
            )
            session.add(alert)
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
            session.flush()
            session.refresh(alert)
            formatted_event.event_id = str(alert.id)
            alert_dto = AlertDto(**formatted_event.dict())

            # Mapping
            try:
                enrichments_bl.run_mapping_rules(alert_dto)
            except Exception:
                logger.exception("Failed to run mapping rules")

            alert_enrichment = get_enrichment(
                tenant_id=tenant_id, fingerprint=formatted_event.fingerprint
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
    pusher_client = get_pusher_client()

    # first, filter out any deduplicated events
    alert_deduplicator = AlertDeduplicator(tenant_id)

    for event in formatted_events:
        event_hash, event_deduplicated = alert_deduplicator.is_deduplicated(event)
        event.alert_hash = event_hash
        event.isDuplicate = event_deduplicated

    # filter out the deduplicated events
    deduplicated_events = list(
        filter(lambda event: event.isDuplicate, formatted_events)
    )
    formatted_events = list(
        filter(lambda event: not event.isDuplicate, formatted_events)
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

    # Now we need to run the rules engine
    try:
        rules_engine = RulesEngine(tenant_id=tenant_id)
        grouped_alerts = rules_engine.run_rules(formatted_events)
        # if new grouped alerts were created, we need to push them to the client
        if grouped_alerts:
            logger.info("Adding group alerts to the workflow manager queue")
            workflow_manager.insert_events(tenant_id, grouped_alerts)
            logger.info("Added group alerts to the workflow manager queue")
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
    if pusher_client:
        try:
            pusher_client.trigger(
                f"private-{tenant_id}",
                "poll-alerts",
                "{}",
            )
        except Exception:
            logger.exception("Failed to push alert to the client")

    # Now we need to update the presets
    try:
        presets = get_all_presets(tenant_id)
        presets_do_update = []
        for preset in presets:
            # filter the alerts based on the search query
            preset_dto = PresetDto(**preset.dict())
            filtered_alerts = RulesEngine.filter_alerts(
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
        # send with pusher
        if pusher_client:
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
):
    extra_dict = {
        "tenant_id": tenant_id,
        "provider_type": provider_type,
        "provider_id": provider_id,
        "fingerprint": fingerprint,
        "event_type": str(type(event)),
        "trace_id": trace_id,
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
            event = enrichments_bl.run_extraction_rules(event)
        except Exception:
            logger.exception("Failed to run pre-formatting extraction rules")

        if provider_type is not None and isinstance(event, dict):
            provider_class = ProvidersFactory.get_provider_class(provider_type)
            event = provider_class.format_alert(event, None)

        # In case when provider_type is not set
        if isinstance(event, dict):
            event = [AlertDto(**event)]

        # Prepare the event for the digest
        if isinstance(event, AlertDto):
            event = [event]

        __internal_prepartion(event, fingerprint, api_key_name)
        __handle_formatted_events(
            tenant_id,
            provider_type,
            session,
            raw_event,
            event,
            provider_id,
        )
    except Exception:
        logger.exception("Error processing event", extra=extra_dict)
        raise Retry(defer=ctx["job_try"] * TIMES_TO_RETRY_JOB)
    finally:
        session.close()
    logger.info("Event processed", extra=extra_dict)
