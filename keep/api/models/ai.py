from datetime import datetime

from pydantic.main import BaseModel


class IncidentMineConfiguration(BaseModel):
    alert_lower_timestamp: datetime = None
    alert_upper_timestamp: datetime = None
    use_n_historical_alerts: int = None
    incident_lower_timestamp: datetime = None
    incident_upper_timestamp: datetime = None
    use_n_hist_incidents: int = None
    pmi_threshold: float = 0.0
    knee_threshold: float = 0.8
    min_incident_size: int = 5
    min_alert_number: int = 100
    incident_similarity_threshold: float = 0.8
    general_temp_dir: str = None
    sliding_window: int = 1 * 60 * 60
