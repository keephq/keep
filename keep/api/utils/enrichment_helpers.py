import logging
from datetime import datetime
from typing import Optional

from opentelemetry import trace
from sqlmodel import Session

from keep.api.core.db import existed_or_new_session
from keep.api.models.alert import (
    AlertDto,
    AlertStatus,
    AlertWithIncidentLinkMetadataDto,
)
from keep.api.models.db.alert import Alert, LastAlertToIncident

tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)


def javascript_iso_format(last_received: str) -> str:
    """
    https://stackoverflow.com/a/63894149/12012756
    """
    dt = datetime.fromisoformat(last_received)
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_and_enrich_deleted_and_assignees(alert: AlertDto, enrichments: dict):
    # tb: we'll need to refactor this at some point since its flaky
    # assignees and deleted are special cases that we need to handle
    # they are kept as a list of timestamps and we need to check if the
    # timestamp of the alert is in the list, if it is, it means that the
    # alert at that specific time was deleted or assigned.
    #
    # THIS IS MAINLY BECAUSE WE ALSO HAVE THE PULLED ALERTS,
    # OTHERWISE, WE COULD'VE JUST UPDATE THE ALERT IN THE DB
    deleted_last_received = enrichments.get(
        "deletedAt", enrichments.get("deleted", [])
    )  # "deleted" is for backward compatibility
    if javascript_iso_format(alert.lastReceived) in deleted_last_received:
        alert.deleted = True
    assignees: dict = enrichments.get("assignees", {})
    assignee = assignees.get(alert.lastReceived) or assignees.get(
        javascript_iso_format(alert.lastReceived)
    )
    if assignee:
        alert.assignee = assignee

    alert.enriched_fields = list(
        filter(lambda x: not x.startswith("disposable_"), list(enrichments.keys()))
    )
    if "assignees" in alert.enriched_fields:
        # User can't be un-assigned. Just re-assigned to someone else
        alert.enriched_fields.remove("assignees")


def calculated_start_firing_time(
    alert: AlertDto, previous_alert: AlertDto | list[AlertDto]
) -> str:
    """
    Calculate the start firing time of an alert based on the previous alert.

    Args:
        alert (AlertDto): The alert to calculate the start firing time for.
        previous_alert (AlertDto): The previous alert.

    Returns:
        str: The calculated start firing time.
    """
    # if the alert is not firing, there is no start firing time
    if alert.status != AlertStatus.FIRING.value:
        return None
    # if this is the first alert, the start firing time is the same as the last received time
    if not previous_alert:
        return alert.lastReceived
    elif isinstance(previous_alert, list):
        previous_alert = previous_alert[0]
    # else, if the previous alert was firing, the start firing time is the same as the previous alert
    if previous_alert.status == AlertStatus.FIRING.value:
        return previous_alert.firingStartTime
    # else, if the previous alert was resolved, the start firing time is the same as the last received time
    else:
        return alert.lastReceived


def calculated_firing_counter(
    alert: AlertDto, previous_alert: AlertDto | list[AlertDto]
) -> int:
    """
    Calculate the firing counter of an alert based on the previous alert.

    Args:
        alert (AlertDto): The alert to calculate the firing counter for.
        previous_alert (AlertDto): The previous alert.

    Returns:
        int: The calculated firing counter.
    """
    # if its an acknowledged alert, the firing counter is 0

    if alert.status == AlertStatus.ACKNOWLEDGED.value:
        return 0

    # if this is the first alert, the firing counter is 1
    if not previous_alert:
        return 1
    elif isinstance(previous_alert, list):
        previous_alert = previous_alert[0]

    if previous_alert.status == AlertStatus.ACKNOWLEDGED.value:
        return 1

    # else, increment counter if the previous alert was firing
    # NOTE: firingCounter -> 0 only if acknowledged
    return previous_alert.firingCounter + 1


def convert_db_alerts_to_dto_alerts(
    alerts: list[Alert | tuple[Alert, LastAlertToIncident]],
    with_incidents: bool = False,
    with_alert_instance_enrichment: bool = False,
    session: Optional[Session] = None,
) -> list[AlertDto | AlertWithIncidentLinkMetadataDto]:
    """
    Enriches the alerts with the enrichment data.

    Args:
        alerts (list[Alert]): The alerts to enrich.
        with_incidents (bool): enrich with incidents data

    Returns:
        list[AlertDto | AlertWithIncidentLinkMetadataDto]: The enriched alerts.
    """
    with existed_or_new_session(session) as session:
        alerts_dto = []
        with tracer.start_as_current_span("alerts_enrichment"):
            # enrich the alerts with the enrichment data
            for _object in alerts:

                # We may have an Alert only or and Alert with an LastAlertToIncident
                if isinstance(_object, Alert):
                    alert, alert_to_incident = _object, None
                else:
                    alert, alert_to_incident = _object

                enrichments = {}
                if with_alert_instance_enrichment and alert.alert_instance_enrichment:
                    enrichments = alert.alert_instance_enrichment.enrichments
                elif alert.alert_enrichment and not with_alert_instance_enrichment:
                    enrichments = alert.alert_enrichment.enrichments

                alert.event.update(enrichments)

                if with_incidents:
                    if alert._incidents:
                        alert.event["incident"] = ",".join(
                            str(incident.id) for incident in alert._incidents
                        )
                try:
                    if alert_to_incident is not None:
                        alert_dto = AlertWithIncidentLinkMetadataDto.from_db_instance(
                            alert, alert_to_incident
                        )
                    else:
                        alert_dto = AlertDto(**alert.event)

                    if enrichments:
                        parse_and_enrich_deleted_and_assignees(alert_dto, enrichments)

                except Exception:
                    # should never happen but just in case
                    logger.exception(
                        "Failed to parse alert",
                        extra={
                            "alert": alert,
                        },
                    )
                    continue

                alert_dto.event_id = str(alert.id)

                # if the alert is acknowledged, the firing counter is 0
                if alert_dto.status == AlertStatus.ACKNOWLEDGED.value:
                    alert_dto.firingCounter = 0

                # enrich provider id when it's possible
                if alert_dto.providerId is None:
                    alert_dto.providerId = alert.provider_id
                    alert_dto.providerType = alert.provider_type
                alerts_dto.append(alert_dto)
    return alerts_dto
