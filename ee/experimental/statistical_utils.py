import numpy as np
import pandas as pd

from typing import List, Tuple

def get_batched_alert_counts(alerts: pd.DataFrame, unique_alert_identifier: str, sliding_window_size: int, step_size: int) -> pd.DataFrame:
    """
        This function calculates number of alerts per sliding window.
        
        Parameters:
        alerts (pd.DataFrame): a DataFrame containing alerts
        unique_alert_identifier (str): a unique identifier for alerts
        sliding_window_size (int): sliding window size in seconds
        step_size (int): step size in seconds
        
        Returns:
        rolling_counts (pd.DataFrame): a DataFrame containing the number of alerts per sliding window
    """
    
    resampled_alert_counts = alerts.set_index('starts_at').resample(f'{step_size}s')[unique_alert_identifier].value_counts().unstack(fill_value=0)
    rolling_counts = resampled_alert_counts.rolling(window=f'{sliding_window_size}s', min_periods=1).sum()

    return rolling_counts
    

def get_batched_alert_occurrences(alerts: pd.DataFrame, unique_alert_identifier: str, sliding_window_size: int, step_size: int) -> pd.DataFrame:
    """
        This function calculates occurrences of alerts per sliding window.
        
        Parameters:
        alerts (pd.DataFrame): a DataFrame containing alerts
        unique_alert_identifier (str): a unique identifier for alerts
        sliding_window_size (int): sliding window size in seconds
        step_size (int): step size in seconds
        
        Returns:
        alert_occurences (pd.DataFrame): a DataFrame containing the occurrences of alerts per sliding window
    """
    
    alert_counts  = get_batched_alert_counts(alerts, unique_alert_identifier, sliding_window_size, step_size)
    alert_occurences = pd.DataFrame(np.where(alert_counts > 0, 1, 0), index=alert_counts.index, columns=alert_counts.columns)
    
    return alert_occurences

def get_jaccard_scores(P_a: np.array, P_aa: np.array) -> np.array:
    """
        This function calculates the Jaccard similarity scores between recurring events.
        
        Parameters:
        P_a (np.array): a 1D array containing the probabilities of events
        P_aa (np.array): a 2D array containing the probabilities of joint events
        
        Returns:
        jaccard_matrix (np.array): a 2D array containing the Jaccard similarity scores between events
    """
    
    P_a_matrix = P_a[:, None] + P_a
    union_matrix = P_a_matrix - P_aa
    
    with np.errstate(divide='ignore', invalid='ignore'):
        jaccard_matrix = np.where(union_matrix != 0, P_aa / union_matrix, 0)
    
    np.fill_diagonal(jaccard_matrix, 1)
    
    return jaccard_matrix
    

def get_alert_jaccard_matrix(alerts: pd.DataFrame, unique_alert_identifier: str, sliding_window_size: int, step_size: int) -> pd.DataFrame:
    """
        This function calculates Jaccard similarity scores between alert groups (fingerprints).
        
        Parameters:
        alerts (pd.DataFrame): a DataFrame containing alerts
        unique_alert_identifier (str): a unique identifier for alerts
        sliding_window_size (int): sliding window size in seconds
        step_size (int): step size in seconds
        
        Returns:
        jaccard_scores_df (pd.DataFrame): a DataFrame containing the Jaccard similarity scores between alert groups        
    """
    
    alert_occurrences_df = get_batched_alert_occurrences(alerts, unique_alert_identifier, sliding_window_size, step_size)
    alert_occurrences = alert_occurrences_df.to_numpy()
    
    alert_probabilities = np.mean(alert_occurrences, axis=0)
    joint_alert_occurrences = np.dot(alert_occurrences.T, alert_occurrences)
    pairwise_alert_probabilities = joint_alert_occurrences / alert_occurrences.shape[0]
    
    jaccard_scores = get_jaccard_scores(alert_probabilities, pairwise_alert_probabilities)
    jaccard_scores_df = pd.DataFrame(jaccard_scores, index=alert_occurrences_df.columns, columns=alert_occurrences_df.columns)
    
    return jaccard_scores_df
    
    
def get_alert_pmi_matrix(alerts: pd.DataFrame, unique_alert_identifier: str, sliding_window_size: int, step_size: int) -> pd.DataFrame:
    """
        This funciton calculates PMI scores between alert groups (fingerprints).
        
        Parameters:
        alerts (pd.DataFrame): a DataFrame containing alerts
        unique_alert_identifier (str): a unique identifier for alerts
        sliding_window_size (int): sliding window size in seconds
        step_size (int): step size in seconds
        
        Returns:
        pmi_matrix_df (pd.DataFrame): a DataFrame containing the PMI scores between
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