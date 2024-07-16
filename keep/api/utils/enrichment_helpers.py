import logging
from datetime import datetime

from opentelemetry import trace

from keep.api.models.alert import AlertDto
from keep.api.models.db.alert import Alert

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


def convert_db_alerts_to_dto_alerts(alerts: list[Alert]) -> list[AlertDto]:
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
            try:
                alert_dto = AlertDto(**alert.event)
                if alert.alert_enrichment:
                    parse_and_enrich_deleted_and_assignees(
                        alert_dto, alert.alert_enrichment.enrichments
                    )
            except Exception:
                # should never happen but just in case
                logger.exception(
                    "Failed to parse alert",
                    extra={
                        "alert": alert,
                    },
                )
                continue
            # enrich provider id when it's possible
            if alert_dto.providerId is None:
                alert_dto.providerId = alert.provider_id
                alert_dto.providerType = alert.provider_type
            alerts_dto.append(alert_dto)
    return alerts_dto
