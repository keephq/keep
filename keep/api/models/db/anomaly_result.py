from datetime import datetime
from sqlmodel import Field, SQLModel
from uuid import uuid4


class AnomalyResult(SQLModel, table=True):
    """Store anomaly detection results for alerts."""

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(index=True)
    alert_fingerprint: str = Field(index=True)
    is_anomaly: bool = Field(default=False)
    anomaly_score: float = Field(default=0.0)
    confidence: float = Field(default=0.0)
    explanation: str = Field(default="")
    timestamp: datetime = Field(default_factory=datetime.now)