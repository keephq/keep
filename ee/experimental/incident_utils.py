import logging
import os

import networkx as nx

from tqdm import tqdm
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple
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
    write_tenant_ai_metadata_to_temp_file,
    get_tenant_ai_metadata_from_temp_file,
)

logger = logging.getLogger(__name__)

ALGORITHM_VERBOSE_NAME = "Correlation algorithm v0.2"
USE_N_HISTORICAL_ALERTS_MINING = 10e4
USE_N_HISTORICAL_ALERTS_PMI = 10e4
USE_N_HISTORICAL_INCIDENTS = 10e4
MIN_ALERT_NUMBER = 100
DEFAULT_TEMP_DIR_LOCATION = "./ee/experimental/ai_temp"


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
    logger.info(
        "Calculating PMI coefficients for alerts",
        extra={
            "tenant_id": tenant_id,
        },
    )

    if not upper_timestamp:
        upper_timestamp = os.environ.get(
            "PMI_ALERT_UPPER_TIMESTAMP", datetime.now())

    if not use_n_historical_alerts:
        use_n_historical_alerts = os.environ.get(
            "PMI_USE_N_HISTORICAL_ALERTS", USE_N_HISTORICAL_ALERTS_PMI
        )

    if not sliding_window:
        sliding_window = os.environ.get("PMI_SLIDING_WINDOW", 4 * 60 * 60)

    if not stride:
        stride = os.environ.get('PMI_STRIDE', int(sliding_window // 4))

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
        tenant_id, limit=use_n_historical_alerts, upper_timestamp=upper_timestamp
    )

    if len(alerts) < min_alert_number:
        logger.info(
            "Not enough alerts to mine incidents",
            extra={
                "tenant_id": tenant_id,
            },
        )
        return {"status": "failed", "message": "Not enough alerts to mine incidents"}

    pmi_matrix, pmi_columns = get_alert_pmi_matrix(
        alerts, "fingerprint", sliding_window, stride, offload_config
    )

    logger.info(
        "Calculating PMI coefficients for alerts finished. PMI matrix is being written to the database.",
        extra={
            "tenant_id": tenant_id,
        },
    )
    write_pmi_matrix_to_temp_file(tenant_id, pmi_matrix, pmi_columns, temp_dir)

    logger.info(
        "PMI matrix is written to the database.",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return {"status": "success"}


def is_similar_incident(incident: Incident, component: Set[str], similarity_threshold: float) -> bool:
    incident_fingerprints = set(alert.fingerprint for alert in incident.alerts)
    intersection = incident_fingerprints.intersection(component)
    component_similarity = len(intersection) / len(component)
    incident_similarity = len(intersection) / len(incident_fingerprints)

    return component_similarity >= similarity_threshold or incident_similarity >= similarity_threshold


def update_existing_incident(incident: Incident, alerts: List[Alert]) -> Tuple[str, bool]:
    add_alerts_to_incident_by_incident_id(incident.tenant_id, incident.id, alerts)
    return incident.id, True


def create_new_incident(component: Set[str], alerts: List[Alert], tenant_id: str) -> Tuple[str, bool]:
    incident_start_time = min(
        alert.timestamp for alert in alerts if alert.fingerprint in component)
    incident_start_time = incident_start_time.replace(microsecond=0)

    incident = create_incident_from_dict(
        tenant_id,
        {
            "name": f"Incident started at {incident_start_time}",
            "description": "Summarization is Disabled",
            "is_predicted": True,
        },
    )
    add_alerts_to_incident_by_incident_id(
        tenant_id,
        incident.id,
        [alert.id for alert in alerts if alert.fingerprint in component],
    )
    return incident.id, False


async def schedule_incident_processing(pool: ArqRedis, tenant_id: str, incident_id: str) -> None:
    job_summary = await pool.enqueue_job(
        "process_summary_generation",
        tenant_id=tenant_id,
        incident_id=incident_id,
    )
    logger.info(
        f"Summary generation for incident {incident_id} scheduled, job: {job_summary}",
        extra={"algorithm": SUMMARY_GENERATOR_VERBOSE_NAME,
               "tenant_id": tenant_id, "incident_id": incident_id},
    )

    job_name = await pool.enqueue_job(
        "process_name_generation",
        tenant_id=tenant_id,
        incident_id=incident_id,
    )
    logger.info(
        f"Name generation for incident {incident_id} scheduled, job: {job_name}",
        extra={"algorithm": NAME_GENERATOR_VERBOSE_NAME,
               "tenant_id": tenant_id, "incident_id": incident_id},
    )


def is_incident_accepting_updates(incident: Incident, current_time: datetime, incident_validity_threshold: timedelta) -> bool:
    return current_time - incident.last_seen_time > incident_validity_threshold


def get_component_first_seen_time(component: Set[str], alerts: List[Alert]) -> datetime:
    return min(alert.timestamp for alert in alerts if alert.fingerprint in component)


def process_component(component: Set[str], incidents: List[Incident], alerts: List[Alert], tenant_id: str, 
                      incident_similarity_threshold: float, min_incident_size: int, incident_validity_threshold: timedelta) -> Tuple[str, bool]:
    logger.info(f'Processing alert graph component with {len(component)} nodes. Min incident size: {min_incident_size}', extra={
                'tenant_id': tenant_id})

    if len(component) < min_incident_size:
        return None, False

    for incident in incidents:
        if is_similar_incident(incident, component, incident_similarity_threshold):
            current_time = get_component_first_seen_time(component, alerts)
            if is_incident_accepting_updates(incident, current_time, incident_validity_threshold):
                logger.info(f'Incident {incident.id} is similar to the alert graph component. Merging...', extra={
                'tenant_id': tenant_id})
                return update_existing_incident(incident, [alert.id for alert in alerts if alert.fingerprint in component])

    logger.info(f'No incident is similar to the alert graph component. Creating new incident...', extra={
                'tenant_id': tenant_id})
    return create_new_incident(component, alerts, tenant_id)


def process_graph_components(graph: nx.Graph, incidents: List[Incident], alerts: List[Alert], tenant_id: str,
                             incident_similarity_threshold: float, min_incident_size: int, incident_validity_threshold: timedelta) -> Tuple[List[str], List[str], List[str]]:
    incident_ids_for_processing = []
    new_incident_ids = []
    updated_incident_ids = []

    for component in nx.connected_components(graph):
        incident_id, is_updated = process_component(
            component, incidents, alerts, tenant_id, incident_similarity_threshold, min_incident_size, incident_validity_threshold)
        if incident_id:
            incident_ids_for_processing.append(incident_id)
            if is_updated:
                updated_incident_ids.append(incident_id)
            else:
                new_incident_ids.append(incident_id)

    return incident_ids_for_processing, new_incident_ids, updated_incident_ids


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


async def mine_incidents_and_create_objects(
    ctx: dict | None,  # arq context
    tenant_id: str,
    alert_lower_timestamp: datetime = None,
    alert_upper_timestamp: datetime = None,
    use_n_historical_alerts: int = None,
    incident_lower_timestamp: datetime = None,
    incident_upper_timestamp: datetime = None,
    use_n_hist_incidents: int = None,
    pmi_threshold: float = None,
    delete_nodes: bool = None,
    knee_threshold: float = None,
    min_incident_size: int = None,
    min_alert_number: int = None,
    incident_similarity_threshold: float = None,
    general_temp_dir: str = None,
    alert_batch_size: int = None,
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
    use_n_hist_incidents (int): number of historical incidents to use
    pmi_threshold (float): PMI threshold used for incident graph edges creation
    knee_threshold (float): knee threshold used for incident graph nodes creation
    min_incident_size (int): minimum incident size
    incident_similarity_threshold (float): incident similarity threshold

    Returns:
    Dict[str, List[Incident]]: a dictionary containing the created incidents
    """

    if not general_temp_dir:
        general_temp_dir = os.environ.get(
            "AI_TEMP_FOLDER", DEFAULT_TEMP_DIR_LOCATION)

    temp_dir = f"{general_temp_dir}/{tenant_id}"
    os.makedirs(temp_dir, exist_ok=True)
    
    metadata = get_tenant_ai_metadata_from_temp_file(temp_dir)
    
    if not incident_upper_timestamp:
        incident_upper_timestamp = os.environ.get(
            "MINE_INCIDENT_UPPER_TIMESTAMP", datetime.now()
        )

    if not incident_lower_timestamp:
        incident_validity = timedelta(
            seconds=int(os.environ.get("MINE_INCIDENT_VALIDITY", "1800"))
        )
        incident_lower_timestamp = incident_upper_timestamp - incident_validity

    if not alert_upper_timestamp:
        alert_upper_timestamp = os.environ.get(
            "MINE_ALERT_UPPER_TIMESTAMP", datetime.now()
        )

    if not alert_lower_timestamp:
        alert_window = timedelta(
            seconds=int(os.environ.get("MINE_ALERT_WINDOW", "1800")))
        alert_lower_timestamp = alert_upper_timestamp - alert_window

    if not use_n_historical_alerts:
        use_n_historical_alerts = os.environ.get(
            "MINE_USE_N_HISTORICAL_ALERTS", USE_N_HISTORICAL_ALERTS_MINING
        )

    if not use_n_hist_incidents:
        use_n_hist_incidents = os.environ.get(
            "MINE_USE_N_HISTORICAL_INCIDENTS", USE_N_HISTORICAL_INCIDENTS
        )

    if not pmi_threshold:
        pmi_threshold = os.environ.get("PMI_THRESHOLD", 0.0)

    if not delete_nodes:
        delete_nodes = os.environ.get("DELETE_NODES", False)

    if not knee_threshold:
        knee_threshold = os.environ.get("KNEE_THRESHOLD", 0.8)

    if not min_incident_size:
        min_incident_size = os.environ.get("MIN_INCIDENT_SIZE", 5)

    if not incident_similarity_threshold:
        incident_similarity_threshold = os.environ.get(
            "INCIDENT_SIMILARITY_THRESHOLD", 0.8
        )
        
    alert_batch_size = int(os.environ.get("MINE_ALERT_WINDOW", 1800)) // 2

    status = calculate_pmi_matrix(
        ctx, tenant_id, min_alert_number=min_alert_number)
    if status.get('status') == 'failed':
        return {"incidents": []}

    logger.info(
        "Getting new alerts",
        extra={
            "tenant_id": tenant_id,
        },
    )
    
    if metadata.get('last_correlated_batch_start', None):
        alert_lower_timestamp = datetime.fromisoformat(metadata.get('last_correlated_batch_start', None))
        alert_lower_timestamp += timedelta(seconds=alert_batch_size)
        
    else: 
        alert_lower_timestamp = None
        
    alerts = query_alerts(
        tenant_id,
        limit=use_n_historical_alerts,
        upper_timestamp=alert_upper_timestamp,
        lower_timestamp=alert_lower_timestamp,
    )
    
    if not alert_lower_timestamp:
        alert_lower_timestamp = min(alert.timestamp for alert in alerts)
    
    n_batches = int((alert_upper_timestamp - alert_lower_timestamp).total_seconds() // alert_batch_size)
    logging.info(f'Starting alert correlatiion. Current batch size: {alert_batch_size} seconds. Number of batches to process: {n_batches}')
    ##### WARNING: This is a temporary solution to the problem of incident validity threshold. It is not a good solution.
    incident_validity_threshold = timedelta(seconds=4*60*60)
    pool = await get_pool() if not ctx else ctx["redis"]
    
    new_incident_ids = []
    updated_incident_ids = []
    
    for batch_idx in tqdm(range(0, n_batches), desc='Processing batches of alerts...'):
        batch_start_timestamp = alert_lower_timestamp + timedelta(seconds=batch_idx*alert_batch_size)
        batch_end_timestamp = batch_start_timestamp + timedelta(seconds=alert_batch_size)
        
        logger.info(f'Processing batch {batch_idx} with start timestamp {batch_start_timestamp} and end timestamp {batch_end_timestamp}')
        
        batch_alerts = [alert for alert in alerts if alert.timestamp < batch_end_timestamp and alert.timestamp >= batch_start_timestamp]
        batch_fingerprints = list(set([alert.fingerprint for alert in batch_alerts]))
        
        batch_incidents, _ = get_last_incidents(
            tenant_id,
            limit=use_n_hist_incidents,
            upper_timestamp=batch_start_timestamp,
            lower_timestamp=batch_start_timestamp - incident_validity_threshold,
            is_predicted=True
        )
        
        logger.info(f'Found {len(batch_incidents)} open incidents at {batch_start_timestamp}. Processing...')
        for incident in batch_incidents:
            incident_fingerprints = set(alert.fingerprint for alert in incident.alerts)
            if len(incident_fingerprints.intersection(set(batch_fingerprints))) == 0:
                continue
            
            incident_fingerprints = list(incident_fingerprints)
            appendable_alerts = [alert for alert in batch_alerts if alert.fingerprint in incident_fingerprints]
            appendable_alerts.sort(key=lambda x: x.timestamp)
            
            
            current_time = get_component_first_seen_time(incident_fingerprints, batch_alerts)
            # WE assume that incident validity threshold is greater than a size of a batch
            if is_incident_accepting_updates(incident, current_time, incident_validity_threshold):
                logger.info(f'Incident {incident.id} is accepting updates. Appending {len(appendable_alerts)} alerts.')
                update_existing_incident(incident, appendable_alerts)
        
        logger.info(f'Looking for new incidents...')
        
        logger.info(
        "Building alert graph",
        extra={
                "tenant_id": tenant_id,
            },  
        )
        
        batch_graph = create_graph(
            tenant_id, batch_fingerprints, temp_dir, pmi_threshold, delete_nodes, knee_threshold
        )

        logger.info(
            "Analyzing alert graph",
            extra={
                "tenant_id": tenant_id,
            },
        )
        
        batch_incident_ids_for_processing, batch_new_incident_ids, batch_updated_incident_ids = process_graph_components(
        batch_graph, batch_incidents, batch_alerts, tenant_id, incident_similarity_threshold, min_incident_size, incident_validity_threshold
        )
        

        for incident_id in batch_incident_ids_for_processing:
            await schedule_incident_processing(pool, tenant_id, incident_id)
        
        new_incident_ids.extend(batch_new_incident_ids)
        updated_incident_ids.extend(batch_updated_incident_ids)
        
    metadata['last_correlated_batch_start'] = str(alert_lower_timestamp + timedelta(seconds=batch_idx*alert_batch_size))
    write_tenant_ai_metadata_to_temp_file(metadata, temp_dir)
    
    new_incident_count = len(set(new_incident_ids))
    updated_incident_count = len(set(updated_incident_ids).difference(set(new_incident_ids)))
    
    incident_ids = list(set(new_incident_ids + updated_incident_ids))
        
    # fingerprints = list(set([alert.fingerprint for alert in alerts]))

    # logger.info(
    #     "Building alert graph",
    #     extra={
    #         "tenant_id": tenant_id,
    #     },
    # )

    # graph = create_graph(
    #     tenant_id, fingerprints, temp_dir, pmi_threshold, delete_nodes, knee_threshold
    # )
    # ids = []

    # logger.info(
    #     "Analyzing alert graph",
    #     extra={
    #         "tenant_id": tenant_id,
    #     },
    # )

    # incident_ids_for_processing, new_incident_count, updated_incident_count = process_graph_components(
    #     graph, incidents, alerts, tenant_id, incident_similarity_threshold, min_incident_size
    # )

    # pool = await get_pool() if not ctx else ctx["redis"]

    # for incident_id in incident_ids_for_processing:
    #     await schedule_incident_processing(pool, tenant_id, incident_id)

    pusher_client = get_pusher_client()
    if pusher_client:
        if new_incident_count > 0 or updated_incident_count > 0:
            log_string = f'{ALGORITHM_VERBOSE_NAME} successfully executed. {new_incident_count} new incidents were created \
                and {updated_incident_count} incidents were updated.'

        else:
            log_string = f'{ALGORITHM_VERBOSE_NAME} successfully executed. {new_incident_count} new incidents were created \
                and {updated_incident_count} incidents were updated. This may be due to high alert sparsity or low amount \
                of unique alert fingerprints. Increasing "sliding window size" or decreasing "minimal amount of unique \
                fingerprints in an incident" configuration parameters may help.'

        pusher_client.trigger(
            f"private-{tenant_id}",
            "ai-logs-change",
            {"log": log_string},
        )
    logger.info(
        "Client notified on new AI log",
        extra={"tenant_id": tenant_id},
    )

    return {
        "incidents": [get_incident_by_id(tenant_id, incident_id) for incident_id in incident_ids]
    }
