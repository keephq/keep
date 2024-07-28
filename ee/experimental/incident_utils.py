import logging

import numpy as np
import pandas as pd
import networkx as nx

from typing import List

from datetime import datetime, timedelta

from fastapi import Depends

from ee.experimental.note_utils import NodeCandidateQueue, NodeCandidate
from ee.experimental.graph_utils import create_graph
from ee.experimental.statistical_utils import get_alert_pmi_matrix

from keep.api.models.db.alert import Alert
from keep.api.core.db import (
    assign_alert_to_incident,
    get_last_alerts,
    create_incident_from_dict,
)

from keep.api.core.dependencies import (
    AuthenticatedEntity,
    AuthVerifier,
)

from keep.api.core.db import (
    assign_alert_to_incident,
    create_incident_from_dict,
    get_incident_by_id,
    get_last_alerts,
    get_last_incidents,
    write_pmi_matrix_to_db,
)

logger = logging.getLogger(__name__)


def calculate_pmi_matrix(
    ctx: dict | None,  # arq context
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
    upper_timestamp: datetime = datetime.now() - timedelta(seconds=60 * 60),
    use_n_historical_alerts: int = 10e10,
    sliding_window: int = 4 * 60 * 60,
    stride: int = 60 * 60,
) -> dict:
    
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Calculating PMI coefficients for alerts",
        extra={
            "tenant_id": tenant_id,
        },
    )
    alerts=get_last_alerts(tenant_id, limit=use_n_historical_alerts, upper_timestamp=upper_timestamp) 
    pmi_matrix = get_alert_pmi_matrix(alerts, 'fingerprint', sliding_window, stride)
    write_pmi_matrix_to_db(tenant_id, pmi_matrix)
    
    return {"status": "success"}


async def mine_incidents_and_create_objects(
        ctx: dict | None,  # arq context
        authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
        alert_lower_timestamp: datetime = datetime.now() - timedelta(seconds=60 * 60 * 60),
        alert_upper_timestamp: datetime = datetime.now(),
        use_n_historical_alerts: int = 10e10,
        incident_lower_timestamp: datetime = datetime.now() - timedelta(seconds=60 * 4 * 60 * 60),
        incident_upper_timestamp: datetime = datetime.now(),
        use_n_hist_incidents: int = 10e10,
        pmi_threshold: float = 0.0,
        knee_threshold: float = 0.8,
        min_incident_size: int = 5,
        incident_similarity_threshold: float = 0.8,
    ):

    calculate_pmi_matrix(ctx, authenticated_entity)

    tenant_id = authenticated_entity.tenant_id
    alerts = get_last_alerts(tenant_id, limit=use_n_historical_alerts, upper_timestamp=alert_upper_timestamp, lower_timestamp=alert_lower_timestamp)
    incidents, _ = get_last_incidents(tenant_id, limit=use_n_hist_incidents, upper_timestamp=incident_upper_timestamp, lower_timestamp=incident_lower_timestamp)
    nc_queue = NodeCandidateQueue()
    
    for candidate in [NodeCandidate(alert.fingerprint, alert.timestamp) for alert in alerts]:
        nc_queue.push_candidate(candidate)
    candidates = nc_queue.get_candidates()          
    
    graph = create_graph(tenant_id, [candidate.fingerprint for candidate in candidates], pmi_threshold, knee_threshold)
    ids = []
    
    for component in nx.connected_components(graph):
        if len(component) > min_incident_size:            
            alerts_appended = False
            for incident in incidents:
                incident_fingerprints = set([alert.fingerprint for alert in incident.alerts])        
                intersection = incident_fingerprints.intersection(component)
        
                if len(intersection) / len(component) >= incident_similarity_threshold:
                    alerts_appended = True
                    for alert in [alert for alert in alerts if alert.fingerprint in component]:
                        assign_alert_to_incident(alert.id, incident.id, tenant_id)
                    
            if not alerts_appended:
                incident_id = create_incident_from_dict(tenant_id, {"name": "Mined using algorithm", "description": "Candidate", "is_predicted": True}).id
                ids.append(incident_id)
                for alert in [alert for alert in alerts if alert.fingerprint in component]:
                    assign_alert_to_incident(alert.id, incident_id, tenant_id)

    return {"incidents": [get_incident_by_id(tenant_id, incident_id) for incident_id in ids]}


def mine_incidents(alerts: List[Alert], incident_sliding_window_size: int=6*24*60*60, statistic_sliding_window_size: int=60*60, 
                   jaccard_threshold: float=0.0, fingerprint_threshold: int=1):
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