import logging
from typing import List, Tuple

import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)


def detect_knee_1d_auto_increasing(y: List[float]) -> Tuple[int, float]:
    """
    This function detects the knee point in an increasing 1D curve. Knee point is the point where a curve
    starts to flatten out (https://en.wikipedia.org/wiki/Knee_of_a_curve).

    Parameters:
    y (List[float]): a list of float values

    Returns:
    tuple: knee_index, knee_y
    """

    def detect_knee_1d(
        y: List[float], curve: str, direction: str = "increasing"
    ) -> Tuple[int, float, List[float]]:
        x = np.arange(len(y))

        x_norm = (x - np.min(x)) / (np.max(x) - np.min(x))
        y_norm = (y - np.min(y)) / (np.max(y) - np.min(y))

        diff_curve = y_norm - x_norm

        if curve == "concave":
            knee_index = np.argmax(diff_curve)
        else:
            knee_index = np.argmin(diff_curve)

        knee_y = y[knee_index]

        return knee_index, knee_y, diff_curve

    knee_index_concave, knee_y_concave, diff_curve_concave = detect_knee_1d(
        y, "concave"
    )
    knee_index_convex, knee_y_convex, diff_curve_convex = detect_knee_1d(y, "convex")
    max_diff_concave = np.max(np.abs(diff_curve_concave))
    max_diff_convex = np.max(np.abs(diff_curve_convex))

    if max_diff_concave > max_diff_convex:
        return knee_index_concave, knee_y_concave
    else:
        return knee_index_convex, knee_y_convex


def create_graph(
    tenant_id: str,
    fingerprints: List[str],
    pmi_values: np.ndarray,
    fingerprint2idx: dict,
    pmi_threshold: float = 0.0,
    delete_nodes: bool = False,
    knee_threshold: float = 0.8,
) -> nx.Graph:
    """
    This function creates a graph from a list of fingerprints. The graph is created based on the PMI values between
    the fingerprints. The edges are created between the fingerprints that have a PMI value greater than the threshold.
    The nodes are removed if the knee point of the PMI values of the edges connected to the node is less than the threshold.

    Parameters:
    tenant_id (str): tenant id
    fingerprints (List[str]): a list of fingerprints
    pmi_threshold (float): PMI threshold
    knee_threshold (float): knee threshold

    Returns:
    nx.Graph: a graph
    """
    graph = nx.Graph()

    if len(fingerprints) == 1:
        graph.add_node(fingerprints[0])
        return graph

    logger.info("Creating alert graph edges", extra={"tenant_id": tenant_id})

    for idx_i, fingerprint_i in enumerate(fingerprints):
        if fingerprint_i not in fingerprint2idx:
            continue

        for idx_j in range(idx_i + 1, len(fingerprints)):
            fingerprint_j = fingerprints[idx_j]

            if fingerprint_j not in fingerprint2idx:
                continue

            weight = pmi_values[
                fingerprint2idx[fingerprint_i], fingerprint2idx[fingerprint_j]
            ]

            if weight > pmi_threshold:
                graph.add_edge(fingerprint_i, fingerprint_j, weight=weight)

    if delete_nodes:
        nodes_to_delete = []
        logger.info(
            "Preparing candidate nodes for deletion", extra={"tenant_id": tenant_id}
        )

        for node in graph.nodes:
            weights = sorted([edge["weight"] for edge in graph[node].values()])

            knee_index, knee_statistic = detect_knee_1d_auto_increasing(weights)

            if knee_statistic < knee_threshold:
                nodes_to_delete.append(node)

        logger.info(
            f"Removing nodes from graph, {len(nodes_to_delete)} nodes will be removed, {len(graph.nodes) - len(nodes_to_delete)} nodes will be left",
            extra={"tenant_id": tenant_id},
        )
        graph.remove_nodes_from(nodes_to_delete)

    return graph
