import logging
import os
import math

import networkx as nx
import numpy as np

from tqdm import tqdm
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Any
from arq.connections import ArqRedis

from ee.experimental.graph_utils import create_graph
from ee.experimental.statistical_utils import get_alert_pmi_matrix
from ee.experimental.generative_utils import generate_incident_summary, generate_incident_name, \
    SUMMARY_GENERATOR_VERBOSE_NAME, NAME_GENERATOR_VERBOSE_NAME

from keep.api.arq_pool import get_pool
from keep.api.core.dependencies import get_pusher_client
from keep.api.models.db.alert import Alert, Incident
from keep.api.core.db import (
    add_alerts_to_incident_by_incident_id,
    create_incident_from_dict,
    get_incident_by_id,
    get_last_incidents,
    query_alerts,
    update_incident_summary,
    update_incident_name,
    write_pmi_matrix_to_temp_file,
    get_pmi_values_from_temp_file,
    get_tenant_config,
    write_tenant_config,
)

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

def calculate_pmi_matrix(
    ctx: dict | None,  # arq context
    tenant_id: str,
    upper_timestamp: datetime = None,
    use_n_historical_alerts: int = None,
    sliding_window: int = None,
    stride: int = None,
    temp_dir: str = None,
    offload_config: Dict = None,
    min_alert_number: int = None,
) -> dict:
    logger.info("Calculating PMI coefficients for alerts", extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})

    if not upper_timestamp:
        upper_timestamp = os.environ.get("PMI_ALERT_UPPER_TIMESTAMP", datetime.now())

    if not use_n_historical_alerts:
        use_n_historical_alerts = os.environ.get(
            "PMI_USE_N_HISTORICAL_ALERTS", USE_N_HISTORICAL_ALERTS_PMI)

    if not sliding_window:
        sliding_window = os.environ.get("PMI_SLIDING_WINDOW", PMI_SLIDING_WINDOW)

    if not stride:
        stride = os.environ.get("PMI_STRIDE", int(sliding_window // STRIDE_DENOMINATOR))

    if not temp_dir:
        temp_dir = os.environ.get("AI_TEMP_FOLDER", DEFAULT_TEMP_DIR_LOCATION)
        temp_dir = f"{temp_dir}/{tenant_id}"
        os.makedirs(temp_dir, exist_ok=True)

    if not offload_config:
        offload_config = os.environ.get("PMI_OFFLOAD_CONFIG", {})

        if "temp_dir" in offload_config:
            offload_config["temp_dir"] = f'{offload_config["temp_dir"]}/{tenant_id}'
            os.makedirs(offload_config["temp_dir"], exist_ok=True)

    if not min_alert_number:
        min_alert_number = os.environ.get("MIN_ALERT_NUMBER", MIN_ALERT_NUMBER)

    alerts = query_alerts(
        tenant_id, limit=use_n_historical_alerts, upper_timestamp=upper_timestamp, sort_ascending=True)

    if len(alerts) < min_alert_number:
        logger.info("Not enough alerts to mine incidents", extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})
        return {"status": "failed", "message": "Not enough alerts to mine incidents"}

    pmi_matrix, pmi_columns = get_alert_pmi_matrix(
        alerts, "fingerprint", sliding_window, stride, offload_config)

    return {"status": "success", "pmi_matrix": pmi_matrix, "pmi_columns": pmi_columns}


def update_existing_incident(incident: Incident, alerts: List[Alert]) -> Tuple[str, bool]:
    add_alerts_to_incident_by_incident_id(incident.tenant_id, incident.id, alerts)
    return incident.id, True


def create_new_incident(component: Set[str], alerts: List[Alert],
                        tenant_id: str) -> Tuple[str, bool]:
    incident_start_time = min(alert.timestamp for alert in alerts if alert.fingerprint in component)
    incident_start_time = incident_start_time.replace(microsecond=0)

    incident = create_incident_from_dict(tenant_id,
                                         {"ai_generated_name": f"Incident started at {incident_start_time}",
                                          "generated_summary": "Summarization is Disabled",
                                          "is_predicted": True})
    add_alerts_to_incident_by_incident_id(
        tenant_id, incident.id, [
            alert.id for alert in alerts if alert.fingerprint in component],)
    return incident.id, False


async def schedule_incident_processing(pool: ArqRedis, tenant_id: str, incident_id: str) -> None:
    job_summary = await pool.enqueue_job("process_summary_generation", tenant_id=tenant_id, incident_id=incident_id,)
    logger.info(f"Summary generation for incident {incident_id} scheduled, job: {job_summary}", extra={
                "algorithm": SUMMARY_GENERATOR_VERBOSE_NAME, "tenant_id": tenant_id, "incident_id": incident_id},)

    job_name = await pool.enqueue_job("process_name_generation", tenant_id=tenant_id, incident_id=incident_id)
    logger.info(f"Name generation for incident {incident_id} scheduled, job: {job_name}", extra={
                "algorithm": NAME_GENERATOR_VERBOSE_NAME, "tenant_id": tenant_id, "incident_id": incident_id},)


def is_incident_accepting_updates(incident: Incident, current_time: datetime,
                                  incident_validity_threshold: timedelta) -> bool:
    return current_time - incident.last_seen_time < incident_validity_threshold


def get_component_first_seen_time(component: Set[str], alerts: List[Alert]) -> datetime:
    return min(alert.timestamp for alert in alerts if alert.fingerprint in component)


def process_graph_component(component: Set[str], batch_incidents: List[Incident], batch_alerts: List[Alert], batch_fingerprints: Set[str],
                             tenant_id: str, min_incident_size: int, incident_validity_threshold: timedelta) -> Tuple[str, bool]:
    is_component_merged = False
    for incident in batch_incidents:
        incident_fingerprints = set(alert.fingerprint for alert in incident.alerts)
        if incident_fingerprints.issubset(component):
            if not incident_fingerprints.intersection(batch_fingerprints):
                continue
            logger.info(f"Found possible extension for incident {incident.id}",
                        extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})

            amendment_time = get_component_first_seen_time(component, batch_alerts)
            if is_incident_accepting_updates(incident, amendment_time, incident_validity_threshold):
                logger.info(f"Incident {incident.id} is accepting updates.",
                                    extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})

                existing_alert_ids = set([alert.id for alert in incident.alerts])
                appendable_alerts = [alert for alert in batch_alerts if alert.fingerprint in component and not alert.id in existing_alert_ids]

                logger.info(f"Appending {len(appendable_alerts)} alerts to incident {incident.id}",
                                    extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})
                is_component_merged = True
                return update_existing_incident_inmem(incident, appendable_alerts)
            else:
                logger.info(f"Incident {incident.id} is not accepting updates. Aborting merge operation.",
                                    extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})

    if not is_component_merged:
        if len(component) >= min_incident_size:
            logger.info(f"Creating new incident with {len(component)} alerts",
                        extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})
            return create_new_incident_inmem(component, batch_alerts, tenant_id)
        else:
            return None, False


def process_alert_batch(batch_alerts: List[Alert], batch_incidents: list[Incident], tenant_id: str, min_incident_size: int,
                        incident_validity_threshold: timedelta, pmi_values, fingerpint2idx, pmi_threshold, delete_nodes, knee_threshold) -> Tuple[str, bool]:

    batch_fingerprints = set([alert.fingerprint for alert in batch_alerts])

    amended_fingerprints = set(batch_fingerprints)
    for incident in batch_incidents:
        incident_fingerprints = set(alert.fingerprint for alert in incident.alerts)

        amended_fingerprints = incident_fingerprints.union(batch_fingerprints)

    logger.info("Building alert graph", extra={"tenant_id": tenant_id, "algorithm": NAME_GENERATOR_VERBOSE_NAME})
    amended_graph = create_graph(tenant_id, list(amended_fingerprints), pmi_values,
                                                  fingerpint2idx, pmi_threshold, delete_nodes, knee_threshold)

    logger.info("Analyzing alert graph", extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})
    batch_incident_ids_for_processing = []
    batch_new_incidents = []
    batch_updated_incidents = []

    for component in nx.connected_components(amended_graph):
            incident, is_updated = process_graph_component(component, batch_incidents, batch_alerts, batch_fingerprints, tenant_id, min_incident_size, incident_validity_threshold)
            if incident:
                batch_incident_ids_for_processing.append(incident.id)
                if is_updated:
                    batch_updated_incidents.append(incident)
                else:
                    batch_new_incidents.append(incident)

    return batch_incident_ids_for_processing, batch_new_incidents, batch_updated_incidents


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


def get_last_incidents_inmem(incidents: List[Incident], upper_timestamp: datetime, lower_timestamp: datetime) -> List[Incident]:
    return [incident for incident in incidents if lower_timestamp < incident.last_seen_time < upper_timestamp]


def add_alerts_to_incident_by_incident_id_inmem(incident: Incident, alerts: List[str]):
    incident.alerts.extend(alerts)
    return incident


def create_incident_from_dict_inmem(tenant_id: str, incident_dict: Dict[str, Any]) -> Incident:
    return Incident(tenant_id=tenant_id, **incident_dict)


def create_new_incident_inmem(component: Set[str], alerts: List[Alert], tenant_id: str) -> Tuple[Incident, bool]:
    incident_start_time = min(alert.timestamp for alert in alerts if alert.fingerprint in component)
    incident_start_time = incident_start_time.replace(microsecond=0)

    incident = create_incident_from_dict_inmem(tenant_id,
                                         {"name": f"Incident started at {incident_start_time}",
                                          "description": "Summarization is Disabled",
                                          "is_predicted": True})

    incident = add_alerts_to_incident_by_incident_id_inmem(
        incident, [alert for alert in alerts if alert.fingerprint in component],)
    incident.last_seen_time = max([alert.timestamp for alert in incident.alerts])

    return incident, False


def update_existing_incident_inmem(incident: Incident, alerts: List[str]) -> Tuple[str, bool]:
    incident = add_alerts_to_incident_by_incident_id_inmem(incident, alerts)
    incident.last_seen_time = max([alert.timestamp for alert in incident.alerts])
    return incident, True


def update_incident_summary_inmem(incident: Incident, summary: str):
    incident.summary = summary
    return incident


def update_incident_name_inmem(incident: Incident, name: str):
    incident.name = name
    return incident


async def mine_incidents_and_create_objects(
    ctx: dict | None,  # arq context
    tenant_id: str,
    alert_lower_timestamp: datetime = None,
    alert_upper_timestamp: datetime = None,
    use_n_historical_alerts: int = None,
    incident_lower_timestamp: datetime = None,
    incident_upper_timestamp: datetime = None,
    use_n_historical_incidents: int = None,
    pmi_threshold: float = None,
    delete_nodes: bool = None,
    knee_threshold: float = None,
    min_incident_size: int = None,
    min_alert_number: int = None,
    incident_similarity_threshold: float = None,
    incident_validity_threshold: timedelta = None,
    general_temp_dir: str = None,
    alert_validity_threshold: int = None,
    sliding_window: int = None,
) -> Dict[str, List[Incident]]:
    """
    This function mines incidents from alerts and creates incidents in the database.

    Parameters:
    tenant_id (str): tenant id
    alert_lower_timestamp (datetime): lower timestamp for alerts
    alert_upper_timestamp (datetime): upper timestamp for alerts
    use_n_historical_alerts (int): number of historical alerts to use
    incident_lower_timestamp (datetime): lower timestamp for incidents
    incident_upper_timestamp (datetime): upper timestamp for incidents
    use_n_historical_incidents (int): number of historical incidents to use
    pmi_threshold (float): PMI threshold used for incident graph edges creation
    knee_threshold (float): knee threshold used for incident graph nodes creation
    min_incident_size (int): minimum incident size
    min_alert_number (int):  minimal amount of unique alert fingerprints
    incident_similarity_threshold (float): incident similarity threshold
    general_temp_dir (str):
    sliding_window (int): maximal acceptable gap between alerts of the same incident

    Returns:
    Dict[str, List[Incident]]: a dictionary containing the created incidents
    """
    # obtain tenant_config
    if not general_temp_dir:
        general_temp_dir = os.environ.get(
            "AI_TEMP_FOLDER", DEFAULT_TEMP_DIR_LOCATION)

    temp_dir = f"{general_temp_dir}/{tenant_id}"
    os.makedirs(temp_dir, exist_ok=True)

    tenant_config = get_tenant_config(tenant_id)

    # obtain alert-related parameters
    alert_validity_threshold = int(os.environ.get("ALERT_VALIDITY_THRESHOLD", ALERT_VALIDITY_THRESHOLD))
    alert_batch_stride = alert_validity_threshold // STRIDE_DENOMINATOR

    if not alert_upper_timestamp:
        alert_upper_timestamp = os.environ.get(
            "MINE_ALERT_UPPER_TIMESTAMP", datetime.now())

    if not alert_lower_timestamp:
        if tenant_config.get("last_correlated_batch_start", None):
            alert_lower_timestamp = datetime.fromisoformat(
                tenant_config.get("last_correlated_batch_start", None))

        else:
            alert_lower_timestamp = None

    if not use_n_historical_alerts:
        use_n_historical_alerts = os.environ.get(
            "MINE_USE_N_HISTORICAL_ALERTS",
            USE_N_HISTORICAL_ALERTS_MINING)

    # obtain incident-related parameters
    if not incident_validity_threshold:
        incident_validity_threshold = timedelta(
            seconds=int(os.environ.get("MINE_INCIDENT_VALIDITY", INCIDENT_VALIDITY_THRESHOLD)))

    if not use_n_historical_incidents:
        use_n_historical_incidents = os.environ.get(
            "MINE_USE_N_HISTORICAL_INCIDENTS", USE_N_HISTORICAL_INCIDENTS)

    if not incident_similarity_threshold:
        incident_similarity_threshold = os.environ.get("INCIDENT_SIMILARITY_THRESHOLD", 0.8)

    if not min_incident_size:
        min_incident_size = os.environ.get("MIN_INCIDENT_SIZE", 5)

    if not pmi_threshold:
        pmi_threshold = os.environ.get("PMI_THRESHOLD", 0.0)

    if not delete_nodes:
        delete_nodes = os.environ.get("DELETE_NODES", False)

    if not knee_threshold:
        knee_threshold = os.environ.get("KNEE_THRESHOLD", 0.8)

    status = calculate_pmi_matrix(ctx, tenant_id, min_alert_number=min_alert_number, sliding_window=sliding_window)
    if status.get("status") == "failed":
        pusher_client = get_pusher_client()
        if pusher_client:
            log_string = f"{ALGORITHM_VERBOSE_NAME} failed to calculate PMI matrix"
            pusher_client.trigger(f"private-{tenant_id}", "ai-logs-change", {"log": "Failed to calculate PMI matrix"})

        return {"incidents": []}

    elif status.get("status") == "success":
        logger.info(
        f"Calculating PMI coefficients for alerts finished. PMI matrix is being written to the database. Total number of PMI coefficients: {status.get('pmi_matrix').size}",
        extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})

        pmi_values = status.get("pmi_matrix")
        fingerprints = status.get("pmi_columns")
        write_pmi_matrix_to_temp_file(tenant_id, pmi_values, fingerprints, temp_dir)

        logger.info("PMI matrix is written to the database.", extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})
        fingerprint2idx = {fingerprint: i for i, fingerprint in enumerate(fingerprints)}
    logger.info("Getting new alerts and incidents", extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})

    alerts = query_alerts(tenant_id, limit=use_n_historical_alerts, upper_timestamp=alert_upper_timestamp,
        lower_timestamp=alert_lower_timestamp, sort_ascending=True)

    if not alert_lower_timestamp:
        alert_lower_timestamp = min(alert.timestamp for alert in alerts)

    incidents, _ = get_last_incidents(tenant_id, limit=use_n_historical_incidents, upper_timestamp=alert_lower_timestamp + incident_validity_threshold,
                                   lower_timestamp=alert_upper_timestamp - incident_validity_threshold, with_alerts=True)

    n_batches = int(math.ceil((alert_upper_timestamp - alert_lower_timestamp).total_seconds() / alert_batch_stride)) - (STRIDE_DENOMINATOR - 1)
    logging.info(
        f"Starting alert correlation. Current batch size: {alert_validity_threshold} seconds. Current \
            batch stride: {alert_batch_stride} seconds. Number of batches to process: {n_batches}")

    pool = await get_pool() if not ctx else ctx["redis"]

    new_incident_ids = []
    updated_incident_ids = []
    incident_ids_for_processing = []

    alert_timestamps = np.array([alert.timestamp.timestamp() for alert in alerts])
    batch_indices = np.arange(0, n_batches)
    batch_start_ts = alert_lower_timestamp.timestamp() + np.array([batch_idx * alert_batch_stride for batch_idx in batch_indices])
    batch_end_ts = batch_start_ts + alert_validity_threshold

    start_indices = np.searchsorted(alert_timestamps, batch_start_ts, side='left')
    end_indices = np.searchsorted(alert_timestamps, batch_end_ts, side='right')

    for batch_idx, (start_idx, end_idx) in tqdm(enumerate(zip(start_indices, end_indices)), total=n_batches, desc="Processing alert batches.."):
        batch_alerts = alerts[start_idx:end_idx]

        logger.info(
            f"Processing batch {batch_idx} with start timestamp {datetime.fromtimestamp(batch_start_ts[batch_idx])} \
                and end timestamp {min(datetime.fromtimestamp(batch_end_ts[batch_idx]), alert_upper_timestamp)}. Batch size: {len(batch_alerts)}",
            extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})

        if len(batch_alerts) == 0:
            continue

        batch_incidents = get_last_incidents_inmem(incidents, datetime.fromtimestamp(batch_end_ts[batch_idx]),
                                                       datetime.fromtimestamp(batch_start_ts[batch_idx]) - incident_validity_threshold)

        logger.info(
            f"Found {len(batch_incidents)} incidents that accept updates by {datetime.fromtimestamp(batch_start_ts[batch_idx])}.",
            extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})

        batch_incident_ids_for_processing, batch_new_incidents, batch_updated_incidents = process_alert_batch(
            batch_alerts, batch_incidents, tenant_id, min_incident_size, incident_validity_threshold, pmi_values, fingerprint2idx, pmi_threshold, delete_nodes, knee_threshold)

        new_incident_ids.extend([incident.id for incident in batch_new_incidents])
        incidents.extend(batch_new_incidents)
        updated_incident_ids.extend([incident.id for incident in batch_updated_incidents])
        incident_ids_for_processing.extend(batch_incident_ids_for_processing)

    logger.info(f"Saving last correlated batch start timestamp: {datetime.isoformat(alert_lower_timestamp + timedelta(seconds= (n_batches - 1) * alert_batch_stride))}",
                extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})
    tenant_config["last_correlated_batch_start"] = datetime.isoformat(alert_lower_timestamp + timedelta(seconds= (n_batches - 1) * alert_batch_stride))
    write_tenant_config(tenant_id, tenant_config)
    
    logger.info(f"Writing {len(incidents)} incidents to database",
                extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})
    db_incident_ids_for_processing = []
    db_new_incident_ids = []
    db_updated_incident_ids = []
    for incident in incidents:
        if not get_incident_by_id(tenant_id, incident.id):
            incident_dict = {
                "ai_generated_name": incident.ai_generated_name,
                "generated_summary": incident.generated_summary,
                "is_predicted": True,
            }
            db_incident = create_incident_from_dict(tenant_id, incident_dict)

            incident_id = db_incident.id
        else:
            incident_id = incident.id

        if incident.id in incident_ids_for_processing:
            db_incident_ids_for_processing.append(incident_id)
        
        if incident.id in new_incident_ids:
            db_new_incident_ids.append(incident_id)

        if incident.id in updated_incident_ids:
            db_updated_incident_ids.append(incident_id)


        add_alerts_to_incident_by_incident_id(tenant_id, incident_id, [alert.id for alert in incident.alerts])

    logger.info(f"Scheduling {len(db_incident_ids_for_processing)} incidents for name / summary generation",
                extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})
    new_incident_count = len(set(new_incident_ids))
    updated_incident_count = len(set(updated_incident_ids).difference(set(new_incident_ids)))
    db_incident_ids_for_processing = list(set(db_incident_ids_for_processing))
    for incident_id in db_incident_ids_for_processing:
        await schedule_incident_processing(pool, tenant_id, incident_id)

    incident_ids = list(set(db_new_incident_ids + db_updated_incident_ids))

    pusher_client = get_pusher_client()
    if pusher_client:
        if new_incident_count > 0 or updated_incident_count > 0:
            log_string = f"{ALGORITHM_VERBOSE_NAME} successfully executed. Alerts from {alert_lower_timestamp.replace(microsecond=0)} \
                till {alert_upper_timestamp.replace(microsecond=0)} were processed. Total count of processed alerts: {len(alerts)}. \
                    Total count of created incidents: {new_incident_count}. Total count of updated incidents: \
                        {updated_incident_count}."
        elif len(alerts) > 0:
            log_string = f'{ALGORITHM_VERBOSE_NAME} successfully executed. Alerts from {alert_lower_timestamp.replace(microsecond=0)} \
                till {alert_upper_timestamp.replace(microsecond=0)} were processed. Total count of processed alerts: {len(alerts)}. \
                    Total count of created incidents: {new_incident_count}. Total count of updated incidents: \
                        {updated_incident_count}. This may be due to high alert sparsity or low amount of unique \
                            alert fingerprints. Adding more alerts, increasing "sliding window size" or decreasing minimal amount of \
                            "minimal amount of unique fingerprints in an incident" configuration parameters may help.'

        else:
            log_string = f'{ALGORITHM_VERBOSE_NAME} successfully executed. Alerts from {alert_lower_timestamp.replace(microsecond=0)} \
                till {alert_upper_timestamp.replace(microsecond=0)} were processed. Total count of processed alerts: {len(alerts)}. \
                    No incidents were created or updated. Add alerts to the system to enable automatic incident creation.'

        pusher_client.trigger(f"private-{tenant_id}", "ai-logs-change", {"log": log_string})

    logger.info("Client notified on new AI log", extra={"tenant_id": tenant_id, "algorithm": ALGORITHM_VERBOSE_NAME})

    return {"incidents": [get_incident_by_id(tenant_id, incident_id)
                          for incident_id in incident_ids]}