import logging

import numpy as np
import pandas as pd
import networkx as nx

from typing import List

from keep.api.models.db.alert import Alert
from keep.api.core.db import (
    assign_alert_to_incident,
    get_last_alerts,
    create_incident_from_dict,
    get_all_tenants,
)

logger = logging.getLogger(__name__)

async def mine_incidents_and_create_objects(
        ctx: dict | None,  # arq context
        tenant_id: str | None = None,
        use_n_historical_alerts: int = 10000,
        incident_sliding_window_size: int = 6 * 24 * 60 * 60,
        statistic_sliding_window_size: int = 60 * 60,
        jaccard_threshold: float = 0.0,
        fingerprint_threshold: int = 1,
    ):
    if tenant_id is None:
        logger.info("No tenant_id provided, mining incidents for all tenante")
        tenants = get_all_tenants()
        tenant_ids = [tenant.id for tenant in tenants]
    else:
        tenant_ids = [tenant_id]

    for tenant_id in tenant_ids:
        alerts = get_last_alerts(tenant_id, use_n_historical_alerts)
        if len(alerts) > 0:
        
            incidents = mine_incidents(
                alerts,
                incident_sliding_window_size,
                statistic_sliding_window_size,
                jaccard_threshold,
                fingerprint_threshold,
            )

            for incident in incidents:
                incident_id = create_incident_from_dict(
                    tenant_id=tenant_id,
                    incident_data={
                        "name": "Mined using algorithm",
                        "description": "Candidate",
                        "is_predicted": True
                    }
                ).id    

                for alert in incident["alerts"]:
                    assign_alert_to_incident(alert.id, incident_id, tenant_id)
            
            if len(tenant_ids) == 1:
                return {"incidents": incidents}



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