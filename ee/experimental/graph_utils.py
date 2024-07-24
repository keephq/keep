import numpy as np
import networkx as nx

from keep.api.core.db import get_pmi_value


def detect_knee_1d_auto_increasing(y):
    """
    Detect the knee point in an increasing 1D curve automatically.

    Parameters:
    y (array-like): y values of the curve

    Returns:
    int: index of the knee point
    float: y value of the knee point
    """
    def detect_knee_1d(y, curve, direction='increasing'):
        x = np.arange(len(y))

        x_norm = (x - np.min(x)) / (np.max(x) - np.min(x))
        y_norm = (y - np.min(y)) / (np.max(y) - np.min(y))

        diff_curve = y_norm - x_norm

        if curve == 'concave':
            knee_index = np.argmax(diff_curve)
        else:
            knee_index = np.argmin(diff_curve)

        knee_y = y[knee_index]

        return knee_index, knee_y, diff_curve

    knee_index_concave, knee_y_concave, diff_curve_concave = detect_knee_1d(y, 'concave')
    knee_index_convex, knee_y_convex, diff_curve_convex = detect_knee_1d(y, 'convex')
    max_diff_concave = np.max(np.abs(diff_curve_concave))
    max_diff_convex = np.max(np.abs(diff_curve_convex))

    if max_diff_concave > max_diff_convex:
        return knee_index_concave, knee_y_concave
    else:
        return knee_index_convex, knee_y_convex
    
    
def create_graph(tenant_id, fingerprints, pmi_threshold=0, knee_threshold=0.8):
    graph = nx.Graph()
    
    if len(fingerprints) == 1:
        graph.add_node(fingerprints[0])
        return graph

    for idx_i, fingerprint_i in enumerate(fingerprints):
        if not isinstance(get_pmi_value(tenant_id, fingerprint_i, fingerprint_i), float):
            continue
        
        for idx_j, fingerprint_j in enumerate(fingerprints[idx_i + 1:]):
            if not isinstance(get_pmi_value(tenant_id, fingerprint_i, fingerprint_j), float):
                continue
            
            weight = get_pmi_value(tenant_id, fingerprint_i, fingerprint_j)
            if weight > pmi_threshold:
                graph.add_edge(fingerprint_i, fingerprint_j, weight=weight)
                
    nodes_to_delete = []
    
    for node in graph.nodes:
        # print([edge for edge in graph[node]])
        weights = sorted([edge['weight'] for edge in graph[node].values()])
        
        knee_index, knee_statistic = detect_knee_1d_auto_increasing(weights)
        
        if knee_statistic < knee_threshold:
            nodes_to_delete.append(node)
    
    graph.remove_nodes_from(nodes_to_delete)
    
    return graph