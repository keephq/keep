import os
import logging

import numpy as np
import pandas as pd
import networkx as nx

from typing import List, Dict
from openai import OpenAI

from datetime import datetime, timedelta

from ee.experimental.graph_utils import create_graph
from ee.experimental.statistical_utils import get_alert_pmi_matrix

from keep.api.arq_pool import get_pool
from keep.api.models.db.alert import Alert, Incident
from keep.api.core.db import (
    add_alerts_to_incident_by_incident_id,
    query_alerts,
    get_last_incidents,
    get_incident_by_id,
    write_pmi_matrix_to_temp_file,
    create_incident_from_dict,
    update_incident_summary,
)

from keep.api.core.dependencies import (
    AuthenticatedEntity,
    AuthVerifier,
    get_pusher_client,
)

logger = logging.getLogger(__name__)

ALGORITHM_VERBOSE_NAME = "Correlation algorithm v0.2"
SUMMARY_GENERATOR_VERBOSE_NAME = "Summary generator v0.1"
USE_N_HISTORICAL_ALERTS_MINING = 10e4
USE_N_HISTORICAL_ALERTS_PMI = 10e4
USE_N_HISTORICAL_INCIDENTS = 10e4
MIN_ALERT_NUMBER = 100
DEFAULT_TEMP_DIR_LOCATION = './ee/experimental/ai_temp'
MAX_SUMMARY_LENGTH = 900


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
            'PMI_ALERT_UPPER_TIMESTAMP', datetime.now())

    if not use_n_historical_alerts:
        use_n_historical_alerts = os.environ.get(
            'PMI_USE_N_HISTORICAL_ALERTS', USE_N_HISTORICAL_ALERTS_PMI)

    if not sliding_window:
        sliding_window = os.environ.get('PMI_SLIDING_WINDOW', 4 * 60 * 60)

    if not stride:
        stride = os.environ.get('PMI_STRIDE', 60 * 60)

    if not temp_dir:
        temp_dir = os.environ.get('AI_TEMP_FOLDER', DEFAULT_TEMP_DIR_LOCATION)
        temp_dir = f'{temp_dir}/{tenant_id}'
        os.makedirs(temp_dir, exist_ok=True)

    if not offload_config:
        offload_config = os.environ.get('PMI_OFFLOAD_CONFIG', {})

        if 'temp_dir' in offload_config:
            offload_config['temp_dir'] = f'{offload_config["temp_dir"]}/{tenant_id}'
            os.makedirs(offload_config['temp_dir'], exist_ok=True)

    if not min_alert_number:
        min_alert_number = os.environ.get('MIN_ALERT_NUMBER', MIN_ALERT_NUMBER)

    alerts = query_alerts(
        tenant_id, limit=use_n_historical_alerts, upper_timestamp=upper_timestamp)

    if len(alerts) < min_alert_number:
        logger.info(
            "Not enough alerts to mine incidents",
            extra={
                "tenant_id": tenant_id,
            },
        )
        return {"status": 'failed', "message": "Not enough alerts to mine incidents"}

    pmi_matrix, pmi_columns = get_alert_pmi_matrix(
        alerts, 'fingerprint', sliding_window, stride, offload_config)

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
    knee_threshold: float = None,
    min_incident_size: int = None,
    min_alert_number: int = None,
    incident_similarity_threshold: float = None,
    general_temp_dir: str = None,
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

    if not incident_upper_timestamp:
        incident_upper_timestamp = os.environ.get(
            'MINE_INCIDENT_UPPER_TIMESTAMP', datetime.now())

    if not incident_lower_timestamp:
        incident_validity = timedelta(
            days=int(os.environ.get('MINE_INCIDENT_VALIDITY', "1")))
        incident_lower_timestamp = incident_upper_timestamp - incident_validity

    if not alert_upper_timestamp:
        alert_upper_timestamp = os.environ.get(
            'MINE_ALERT_UPPER_TIMESTAMP', datetime.now())

    if not alert_lower_timestamp:
        alert_window = timedelta(
            hours=int(os.environ.get('MINE_ALERT_WINDOW', "12")))
        alert_lower_timestamp = alert_upper_timestamp - alert_window

    if not use_n_historical_alerts:
        use_n_historical_alerts = os.environ.get(
            'MINE_USE_N_HISTORICAL_ALERTS', USE_N_HISTORICAL_ALERTS_MINING)

    if not use_n_hist_incidents:
        use_n_hist_incidents = os.environ.get(
            'MINE_USE_N_HISTORICAL_INCIDENTS', USE_N_HISTORICAL_INCIDENTS)

    if not pmi_threshold:
        pmi_threshold = os.environ.get('PMI_THRESHOLD', 0.0)

    if not knee_threshold:
        knee_threshold = os.environ.get('KNEE_THRESHOLD', 0.8)

    if not min_incident_size:
        min_incident_size = os.environ.get('MIN_INCIDENT_SIZE', 5)

    if not incident_similarity_threshold:
        incident_similarity_threshold = os.environ.get(
            'INCIDENT_SIMILARITY_THRESHOLD', 0.8)

    if not general_temp_dir:
        general_temp_dir = os.environ.get(
            'AI_TEMP_FOLDER', DEFAULT_TEMP_DIR_LOCATION)

    temp_dir = f'{general_temp_dir}/{tenant_id}'
    os.makedirs(temp_dir, exist_ok=True)

    status = calculate_pmi_matrix(ctx, tenant_id)
    if status.get('status') == 'failed':
        return {"incidents": []}

    logger.info(
        "Getting new alerts and past incients",
        extra={
            "tenant_id": tenant_id,
        },
    )
    alerts = query_alerts(tenant_id, limit=use_n_historical_alerts,
                          upper_timestamp=alert_upper_timestamp, lower_timestamp=alert_lower_timestamp)
    incidents, _ = get_last_incidents(tenant_id, limit=use_n_hist_incidents,
                                      upper_timestamp=incident_upper_timestamp, lower_timestamp=incident_lower_timestamp)
    fingerprints = list(set([alert.fingerprint for alert in alerts]))

    logger.info(
        "Building alert graph",
        extra={
            "tenant_id": tenant_id,
        },
    )

    graph = create_graph(tenant_id, fingerprints, temp_dir,
                         pmi_threshold, knee_threshold)
    ids = []

    logger.info(
        "Analyzing alert graph",
        extra={
            "tenant_id": tenant_id,
        },
    )

    incident_ids_for_summary_generation = []

    for component in nx.connected_components(graph):
        if len(component) > min_incident_size:
            alerts_appended = False
            for incident in incidents:
                incident_fingerprints = set(
                    [alert.fingerprint for alert in incident.alerts])
                intersection = incident_fingerprints.intersection(component)

                if len(intersection) / len(component) >= incident_similarity_threshold:
                    alerts_appended = True

                    add_alerts_to_incident_by_incident_id(tenant_id, incident.id, [
                                                          alert.id for alert in alerts if alert.fingerprint in component])
                    incident_ids_for_summary_generation.append(incident.id)

            if not alerts_appended:
                incident_start_time = min(
                    [alert.timestamp for alert in alerts if alert.fingerprint in component])
                incident_start_time = incident_start_time.replace(
                    microsecond=0)

                incident = create_incident_from_dict(tenant_id,
                                                     {"name": f"Incident started at {incident_start_time}",
                                                      "description": "Summarization is Disabled", "is_predicted": True})
                ids.append(incident.id)

                add_alerts_to_incident_by_incident_id(tenant_id, incident.id, [
                                                      alert.id for alert in alerts if alert.fingerprint in component])
                incident_ids_for_summary_generation.append(incident.id)

    if not ctx:
        pool = get_pool()
    else:
        pool = ctx["redis"]
    for incident_id in incident_ids_for_summary_generation:
        job = await pool.enqueue_job(
            "process_summary_generation",
            tenant_id=tenant_id,
            incident_id=incident_id,
        )
        logger.info(
            f"Summary generation for incident {incident_id} scheduled, job: {job}",
            extra={"algorithm": ALGORITHM_VERBOSE_NAME,
                   "tenant_id": tenant_id, "incident_id": incident_id},
        )

    pusher_client = get_pusher_client()
    if pusher_client:
        pusher_client.trigger(
            f"private-{tenant_id}",
            "ai-logs-change",
            {"log": ALGORITHM_VERBOSE_NAME + " successfully executed."},
        )
    logger.info(
        "Client notified on new AI log",
        extra={"tenant_id": tenant_id},
    )

    return {"incidents": [get_incident_by_id(tenant_id, incident_id) for incident_id in ids]}


def mine_incidents(alerts: List[Alert], incident_sliding_window_size: int = 6*24*60*60, statistic_sliding_window_size: int = 60*60,
                   jaccard_threshold: float = 0.0, fingerprint_threshold: int = 1):
    """
        Mine incidents from alerts.
    """

    alert_dict = {
        'fingerprint': [alert.fingerprint for alert in alerts],
        'timestamp': [alert.timestamp for alert in alerts],
    }
    alert_df = pd.DataFrame(alert_dict)
    mined_incidents = shape_incidents(alert_df, 'fingerprint', incident_sliding_window_size, statistic_sliding_window_size,
                                      jaccard_threshold, fingerprint_threshold)

    return [
        {
            "incident_fingerprint": incident['incident_fingerprint'],
            "alerts": [alert for alert in alerts if alert.fingerprint in incident['alert_fingerprints']],
        }
        for incident in mined_incidents
    ]


def get_batched_alert_counts(alerts: pd.DataFrame, unique_alert_identifier: str, sliding_window_size: int) -> np.ndarray:
    """
        Get the number of alerts in a sliding window.
    """

    resampled_alert_counts = alerts.set_index('timestamp').resample(
        f'{sliding_window_size//2}s')[unique_alert_identifier].value_counts().unstack(fill_value=0)
    rolling_counts = resampled_alert_counts.rolling(
        window=f'{sliding_window_size}s', min_periods=1).sum()
    alert_counts = rolling_counts.to_numpy()

    return alert_counts


def get_batched_alert_occurrences(alerts: pd.DataFrame, unique_alert_identifier: str, sliding_window_size: int) -> np.ndarray:
    """
        Get the occurrence of alerts in a sliding window.
    """

    alert_counts = get_batched_alert_counts(
        alerts, unique_alert_identifier, sliding_window_size)
    alert_occurences = np.where(alert_counts > 0, 1, 0)

    return alert_occurences


def get_jaccard_scores(P_a: np.ndarray, P_aa: np.ndarray) -> np.ndarray:
    """
        Calculate the Jaccard similarity scores between alerts.
    """

    P_a_matrix = P_a[:, None] + P_a
    union_matrix = P_a_matrix - P_aa

    with np.errstate(divide='ignore', invalid='ignore'):
        jaccard_matrix = np.where(union_matrix != 0, P_aa / union_matrix, 0)

    np.fill_diagonal(jaccard_matrix, 1)

    return jaccard_matrix


def get_alert_jaccard_matrix(alerts: pd.DataFrame, unique_alert_identifier: str, sliding_window_size: int) -> np.ndarray:
    """
        Calculate the Jaccard similarity scores between alerts.
    """

    alert_occurrences = get_batched_alert_occurrences(
        alerts, unique_alert_identifier, sliding_window_size)
    alert_probabilities = np.mean(alert_occurrences, axis=0)
    joint_alert_occurrences = np.dot(alert_occurrences.T, alert_occurrences)
    pairwise_alert_probabilities = joint_alert_occurrences / \
        alert_occurrences.shape[0]

    return get_jaccard_scores(alert_probabilities, pairwise_alert_probabilities)


def build_graph_from_occurrence(occurrence_row: pd.DataFrame, jaccard_matrix: np.ndarray, unique_alert_identifiers: List[str],
                                jaccard_threshold: float = 0.05) -> nx.Graph:
    """
        Build a weighted graph using alert occurrence matrix and Jaccard coefficients.
    """

    present_indices = np.where(occurrence_row > 0)[0]

    G = nx.Graph()

    for idx in present_indices:
        alert_desc = unique_alert_identifiers[idx]
        G.add_node(alert_desc)

    for i in present_indices:
        for j in present_indices:
            if i != j and jaccard_matrix[i, j] >= jaccard_threshold:
                alert_i = unique_alert_identifiers[i]
                alert_j = unique_alert_identifiers[j]
                G.add_edge(alert_i, alert_j, weight=jaccard_matrix[i, j])

    return G


def shape_incidents(alerts: pd.DataFrame, unique_alert_identifier: str, incident_sliding_window_size: int, statistic_sliding_window_size: int,
                    jaccard_threshold: float = 0.2, fingerprint_threshold: int = 5) -> List[dict]:
    """
        Shape incidents from alerts.
    """

    incidents = []
    incident_number = 0

    resampled_alert_counts = alerts.set_index('timestamp').resample(
        f'{incident_sliding_window_size//2}s')[unique_alert_identifier].value_counts().unstack(fill_value=0)
    jaccard_matrix = get_alert_jaccard_matrix(
        alerts, unique_alert_identifier, statistic_sliding_window_size)

    for idx in range(resampled_alert_counts.shape[0]):
        graph = build_graph_from_occurrence(
            resampled_alert_counts.iloc[idx], jaccard_matrix, resampled_alert_counts.columns, jaccard_threshold=jaccard_threshold)
        max_component = max(nx.connected_components(graph), key=len)

        min_starts_at = resampled_alert_counts.index[idx]
        max_starts_at = min_starts_at + \
            pd.Timedelta(seconds=incident_sliding_window_size)

        local_alerts = alerts[(alerts['timestamp'] >= min_starts_at) & (
            alerts['timestamp'] <= max_starts_at)]
        local_alerts = local_alerts[local_alerts[unique_alert_identifier].isin(
            max_component)]

        if len(max_component) > fingerprint_threshold:

            incidents.append({
                'incident_fingerprint': f'Incident #{incident_number}',
                'alert_fingerprints': local_alerts[unique_alert_identifier].unique().tolist(),
            })

    return incidents


def generate_incident_summary(incident: Incident, use_n_alerts_for_summary: int = -1, generate_summary: str = None, max_summary_length: int = None) -> str:
    if "OPENAI_API_KEY" not in os.environ:
        logger.error(
            "OpenAI API key is not set. Incident summary generation is not available.")
        return ""

    if not generate_summary:
        generate_summary = os.environ.get("GENERATE_INCIDENT_SUMMARY", "True")

    if generate_summary == "False":
        return ""

    if incident.user_summary:
        return ""

    if not max_summary_length:
        max_summary_length = os.environ.get(
            "MAX_SUMMARY_LENGTH", MAX_SUMMARY_LENGTH)

    if not max_summary_length:
        max_summary_length = os.environ.get(
            "MAX_SUMMARY_LENGTH", MAX_SUMMARY_LENGTH)

    try:
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        incident = get_incident_by_id(incident.tenant_id, incident.id)

        description_strings = np.unique(
            [f'{alert.event["name"]}' for alert in incident.alerts]).tolist()

        if use_n_alerts_for_summary > 0:
            incident_description = "\n".join(
                description_strings[:use_n_alerts_for_summary])
        else:
            incident_description = "\n".join(description_strings)

        timestamps = [alert.timestamp for alert in incident.alerts]
        incident_start = min(timestamps).replace(microsecond=0)
        incident_end = max(timestamps).replace(microsecond=0)

        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

        summary = client.chat.completions.create(model=model, messages=[
            {
                "role": "system",
                "content": f"""You are a very skilled DevOps specialist who can summarize any incident based on alert descriptions. 
                When provided with information, summarize it in a 2-3 sentences explaining what happened and when. 
                ONLY SUMMARIZE WHAT YOU SEE. In the end add information about potential scenario of the incident. 
                When provided with information, answer with max a {int(max_summary_length * 0.9)} symbols excerpt 
                describing incident thoroughly.
                
                EXAMPLE:
                An incident occurred between 2022-11-17 14:11:04 and 2022-11-22 22:19:04, involving a 
                total of 200 alerts. The alerts indicated critical and warning issues such as high CPU and memory 
                usage in pods and nodes, as well as stuck Kubernetes Daemonset rollout. Potential incident scenario: 
                Kubernetes Daemonset rollout stuck due to high CPU and memory usage in pods and nodes. This caused a
                long tail of alerts on various topics."""
            },
            {
                "role": "user",
                "content": f"""Here are  alerts of an incident for summarization:\n{incident_description}\n This incident started  on
                {incident_start}, ended on {incident_end}, included {incident.alerts_count} alerts."""
            }
        ]).choices[0].message.content

        logger.info(f"Generated incident summary with length {len(summary)} symbols",
                    extra={"incident_id": incident.id, "tenant_id": incident.tenant_id})

        if len(summary) > max_summary_length:
            logger.info(f"Generated incident summary is too long. Applying smart truncation",
                        extra={"incident_id": incident.id, "tenant_id": incident.tenant_id})

            summary = client.chat.completions.create(model=model, messages=[
                {
                    "role": "system",
                    "content": f"""You are a very skilled DevOps specialist who can summarize any incident based on a description. 
                    When provided with information, answer with max a {int(max_summary_length * 0.9)} symbols excerpt describing 
                    incident thoroughly.
                    """
                },
                {
                    "role": "user",
                    "content": f"""Here is the description of an incident for summarization:\n{summary}"""
                }
            ]).choices[0].message.content

            logger.info(f"Generated new incident summary with length {len(summary)} symbols",
                        extra={"incident_id": incident.id, "tenant_id": incident.tenant_id})

            if len(summary) > max_summary_length:
                logger.info(f"Generated incident summary is too long. Applying hard truncation",
                            extra={"incident_id": incident.id, "tenant_id": incident.tenant_id})
                summary = summary[: max_summary_length]

        return summary
    except Exception as e:
        logger.error(f"Error in generating incident summary: {e}")
        return ""


async def generate_update_incident_summary(ctx, tenant_id: str, incident_id: str):
    incident = get_incident_by_id(tenant_id, incident_id)
    summary = generate_incident_summary(incident)
    update_incident_summary(tenant_id, incident_id, summary)

    return summary
