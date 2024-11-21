import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set, Tuple

from arq.connections import ArqRedis

from ee.experimental.generative_utils import (
    NAME_GENERATOR_VERBOSE_NAME,
    SUMMARY_GENERATOR_VERBOSE_NAME,
    generate_incident_name,
    generate_incident_summary,
)
from keep.api.core.db import (
    add_alerts_to_incident_by_incident_id,
    create_incident_from_dict,
    get_incident_by_id,
    update_incident_name,
    update_incident_summary,
)
from keep.api.models.db.alert import Alert, Incident

logger = logging.getLogger(__name__)

ALGORITHM_VERBOSE_NAME = "Correlation algorithm v0.2"
USE_N_HISTORICAL_ALERTS_MINING = 10e4
USE_N_HISTORICAL_ALERTS_PMI = 10e4
USE_N_HISTORICAL_INCIDENTS = 10e4
MIN_ALERT_NUMBER = 100
INCIDENT_VALIDITY_THRESHOLD = 3600
ALERT_VALIDITY_THRESHOLD = 3600
# We assume that incident / alert validity threshold is greater than a size of a batch
STRIDE_DENOMINATOR = 4
DEFAULT_TEMP_DIR_LOCATION = "./ee/experimental/ai_temp"
PMI_SLIDING_WINDOW = 3600


def update_existing_incident(
    incident: Incident, alerts: List[Alert]
) -> Tuple[str, bool]:
    add_alerts_to_incident_by_incident_id(incident.tenant_id, incident.id, alerts)
    return incident.id, True


def create_new_incident(
    component: Set[str], alerts: List[Alert], tenant_id: str
) -> Tuple[str, bool]:
    incident_start_time = min(
        alert.timestamp for alert in alerts if alert.fingerprint in component
    )
    incident_start_time = incident_start_time.replace(microsecond=0)

    incident = create_incident_from_dict(
        tenant_id,
        {
            "ai_generated_name": f"Incident started at {incident_start_time}",
            "generated_summary": "Summarization is Disabled",
            "is_predicted": True,
        },
    )
    add_alerts_to_incident_by_incident_id(
        tenant_id,
        incident.id,
        [alert.id for alert in alerts if alert.fingerprint in component],
    )
    return incident.id, False


async def schedule_incident_processing(
    pool: ArqRedis, tenant_id: str, incident_id: str
) -> None:
    job_summary = await pool.enqueue_job(
        "process_summary_generation",
        tenant_id=tenant_id,
        incident_id=incident_id,
    )
    logger.info(
        f"Summary generation for incident {incident_id} scheduled, job: {job_summary}",
        extra={
            "algorithm": SUMMARY_GENERATOR_VERBOSE_NAME,
            "tenant_id": tenant_id,
            "incident_id": incident_id,
        },
    )

    job_name = await pool.enqueue_job(
        "process_name_generation", tenant_id=tenant_id, incident_id=incident_id
    )
    logger.info(
        f"Name generation for incident {incident_id} scheduled, job: {job_name}",
        extra={
            "algorithm": NAME_GENERATOR_VERBOSE_NAME,
            "tenant_id": tenant_id,
            "incident_id": incident_id,
        },
    )


def is_incident_accepting_updates(
    incident: Incident, current_time: datetime, incident_validity_threshold: timedelta
) -> bool:
    return current_time - incident.last_seen_time < incident_validity_threshold


def get_component_first_seen_time(component: Set[str], alerts: List[Alert]) -> datetime:
    return min(alert.timestamp for alert in alerts if alert.fingerprint in component)


def process_graph_component(
    component: Set[str],
    batch_incidents: List[Incident],
    batch_alerts: List[Alert],
    batch_fingerprints: Set[str],
    tenant_id: str,
    min_incident_size: int,
    incident_validity_threshold: timedelta,
) -> Tuple[str, bool]:
    is_component_merged = False
    for incident in batch_incidents:
        incident_fingerprints = set(alert.fingerprint for alert in incident.alerts)
        if incident_fingerprints.issubset(component):
            if not incident_fingerprints.intersection(batch_fingerprints):
                continue
            logger.info(
                f"Found possible extension for incident {incident.id}",
                extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME},
            )

            amendment_time = get_component_first_seen_time(component, batch_alerts)
            if is_incident_accepting_updates(
                incident, amendment_time, incident_validity_threshold
            ):
                logger.info(
                    f"Incident {incident.id} is accepting updates.",
                    extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME},
                )

                existing_alert_ids = set([alert.id for alert in incident.alerts])
                appendable_alerts = [
                    alert
                    for alert in batch_alerts
                    if alert.fingerprint in component
                    and alert.id not in existing_alert_ids
                ]

                logger.info(
                    f"Appending {len(appendable_alerts)} alerts to incident {incident.id}",
                    extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME},
                )
                is_component_merged = True
                return update_existing_incident_inmem(incident, appendable_alerts)
            else:
                logger.info(
                    f"Incident {incident.id} is not accepting updates. Aborting merge operation.",
                    extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME},
                )

    if not is_component_merged:
        if len(component) >= min_incident_size:
            logger.info(
                f"Creating new incident with {len(component)} alerts",
                extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME},
            )
            return create_new_incident_inmem(component, batch_alerts, tenant_id)
        else:
            return None, False


async def generate_update_incident_summary(ctx, tenant_id: str, incident_id: str):
    incident = get_incident_by_id(tenant_id, incident_id)
    summary = generate_incident_summary(incident)

    if summary:
        update_incident_summary(tenant_id, incident_id, summary)

    return summary


async def generate_update_incident_name(ctx, tenant_id: str, incident_id: str):
    incident = get_incident_by_id(tenant_id, incident_id)
    name = generate_incident_name(incident)

    if name:
        update_incident_name(tenant_id, incident_id, name)

    return name


def get_last_incidents_inmem(
    incidents: List[Incident], upper_timestamp: datetime, lower_timestamp: datetime
) -> List[Incident]:
    return [
        incident
        for incident in incidents
        if lower_timestamp < incident.last_seen_time < upper_timestamp
    ]


def add_alerts_to_incident_by_incident_id_inmem(incident: Incident, alerts: List[str]):
    incident.alerts.extend(alerts)
    return incident


def create_incident_from_dict_inmem(
    tenant_id: str, incident_dict: Dict[str, Any]
) -> Incident:
    return Incident(tenant_id=tenant_id, **incident_dict)


def create_new_incident_inmem(
    component: Set[str], alerts: List[Alert], tenant_id: str
) -> Tuple[Incident, bool]:
    incident_start_time = min(
        alert.timestamp for alert in alerts if alert.fingerprint in component
    )
    incident_start_time = incident_start_time.replace(microsecond=0)

    incident = create_incident_from_dict_inmem(
        tenant_id,
        {
            "name": f"Incident started at {incident_start_time}",
            "description": "Summarization is Disabled",
            "is_predicted": True,
        },
    )

    incident = add_alerts_to_incident_by_incident_id_inmem(
        incident,
        [alert for alert in alerts if alert.fingerprint in component],
    )
    incident.last_seen_time = max([alert.timestamp for alert in incident.alerts])

    return incident, False


def update_existing_incident_inmem(
    incident: Incident, alerts: List[str]
) -> Tuple[str, bool]:
    incident = add_alerts_to_incident_by_incident_id_inmem(incident, alerts)
    incident.last_seen_time = max([alert.timestamp for alert in incident.alerts])
    return incident, True


def update_incident_summary_inmem(incident: Incident, summary: str):
    incident.summary = summary
    return incident


def update_incident_name_inmem(incident: Incident, name: str):
    incident.name = name
    return incident
