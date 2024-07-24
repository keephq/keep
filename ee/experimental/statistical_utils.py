import numpy as np
import pandas as pd

def get_batched_alert_counts(alerts, unique_alert_identifier, sliding_window_size, step_size):
    """
        Get the number of alerts in a sliding window.
    """
    
    resampled_alert_counts = alerts.set_index('starts_at').resample(f'{step_size}s')[unique_alert_identifier].value_counts().unstack(fill_value=0)
    rolling_counts = resampled_alert_counts.rolling(window=f'{sliding_window_size}s', min_periods=1).sum()

    return rolling_counts
    

def get_batched_alert_occurrences(alerts, unique_alert_identifier, sliding_window_size, step_size):
    """
        Get the occurrence of alerts in a sliding window.
    """
    
    alert_counts  = get_batched_alert_counts(alerts, unique_alert_identifier, sliding_window_size, step_size)
    alert_occurences = pd.DataFrame(np.where(alert_counts > 0, 1, 0), index=alert_counts.index, columns=alert_counts.columns)
    
    return alert_occurences

def get_jaccard_scores(P_a, P_aa):
    """
        Calculate the Jaccard similarity scores between alerts.
    """
    
    P_a_matrix = P_a[:, None] + P_a
    union_matrix = P_a_matrix - P_aa
    
    with np.errstate(divide='ignore', invalid='ignore'):
        jaccard_matrix = np.where(union_matrix != 0, P_aa / union_matrix, 0)
    
    np.fill_diagonal(jaccard_matrix, 1)
    
    return jaccard_matrix
    

def get_alert_jaccard_matrix(alerts, unique_alert_identifier, sliding_window_size, step_size):
    """
        Calculate the Jaccard similarity scores between alert groups (fingerprints).
    """
    alert_occurrences_df = get_batched_alert_occurrences(alerts, unique_alert_identifier, sliding_window_size, step_size)
    alert_occurrences = alert_occurrences_df.to_numpy()
    
    alert_probabilities = np.mean(alert_occurrences, axis=0)
    joint_alert_occurrences = np.dot(alert_occurrences.T, alert_occurrences)
    pairwise_alert_probabilities = joint_alert_occurrences / alert_occurrences.shape[0]
    
    jaccard_scores = get_jaccard_scores(alert_probabilities, pairwise_alert_probabilities)
    jaccard_scores_df = pd.DataFrame(jaccard_scores, index=alert_occurrences_df.columns, columns=alert_occurrences_df.columns)
    
    return jaccard_scores_df
    
    
def get_alert_pmi_matrix(alerts, unique_alert_identifier, sliding_window_size, step_size):
    """
        Calculate the PMI scores between alert groups (fingerprints).
    """
    alert_dict = {
        'fingerprint': [alert.fingerprint for alert in alerts],
        'starts_at': [alert.timestamp for alert in alerts],
    }
    
    alert_df = pd.DataFrame(alert_dict)
    alert_occurences_df = get_batched_alert_occurrences(alert_df, unique_alert_identifier, sliding_window_size, step_size)
    alert_occurrences = alert_occurences_df.to_numpy()
    alert_probabilities = np.mean(alert_occurrences, axis=0)
    joint_alert_occurrences = np.dot(alert_occurrences.T, alert_occurrences)
    pairwise_alert_probabilities = joint_alert_occurrences / alert_occurrences.shape[0]
    
    pmi_matrix = np.log(pairwise_alert_probabilities / (alert_probabilities[:, None] * alert_probabilities))
    pmi_matrix[np.isnan(pmi_matrix)] = 0
    np.fill_diagonal(pmi_matrix, 0)
    
    pmi_matrix_df = pd.DataFrame(pmi_matrix, index=alert_occurences_df.columns, columns=alert_occurences_df.columns)
    
    return pmi_matrix_df