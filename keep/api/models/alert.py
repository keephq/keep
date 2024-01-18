import logging
from enum import Enum

from pydantic import AnyHttpUrl, BaseModel, Extra, validator

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    # Requires immediate action
    CRITICAL = "critical"
    # Needs to be addressed soon
    HIGH = "high"
    # Indicates a potential problem
    WARNING = "warning"
    # Provides information, no immediate action required
    INFO = "info"
    # Minor issues or lowest priority
    LOW = "low"


class AlertStatus(Enum):
    # Active alert
    FIRING = "firing"
    # Alert has been resolved
    RESOLVED = "resolved"
    # Alert has been acknowledged but not resolved
    ACKNOWLEDGED = "acknowledged"
    # Alert condition is met, but not yet firing
    TRIGGERED = "triggered"
    # Alert is suppressed due to various reasons
    SUPPRESSED = "suppressed"
    # No Data
    PENDING = "pending"


class AlertDto(BaseModel):
    id: str
    name: str
    status: AlertStatus
    severity: AlertSeverity
    lastReceived: str
    environment: str = "undefined"
    isDuplicate: bool | None = None
    duplicateReason: str | None = None
    service: str | None = None
    source: list[str] | None = []
    message: str | None = None
    description: str | None = None
    pushed: bool = False  # Whether the alert was pushed or pulled from the provider
    event_id: str | None = None  # Database alert id
    url: AnyHttpUrl | None = None
    labels: dict | None = {}
    fingerprint: str | None = (
        None  # The fingerprint of the alert (used for alert de-duplication)
    )
    deleted: list[str] = []  # Whether the alert is deleted or not
    providerId: str | None = None  # The provider id

    @validator("fingerprint", pre=True, always=True)
    def assign_fingerprint_if_none(cls, fingerprint, values):
        if fingerprint is None:
            return values.get("name", "")
        return fingerprint

    @validator("deleted", pre=True, always=True)
    def validate_old_deleted(cls, deleted, values):
        """This is a temporary validator to handle the old deleted field"""
        if isinstance(deleted, bool):
            return []
        return deleted

    @validator("severity", pre=True)
    def set_default_severity(cls, v):
        try:
            return AlertSeverity(v)
        except ValueError:
            logging.warning(f"Invalid severity value: {v}")
            # Default value
            return AlertSeverity.INFO

    @validator("status", pre=True)
    def set_default_status(cls, v):
        try:
            return AlertStatus(v)
        except ValueError:
            logging.warning(f"Invalid status value: {v}")
            # Default value
            return AlertStatus.FIRING

    class Config:
        extra = Extra.allow
        schema_extra = {
            "examples": [
                {
                    "id": "1234",
                    "name": "Alert name",
                    "status": "firing",
                    "lastReceived": "2021-01-01T00:00:00.000Z",
                    "environment": "production",
                    "isDuplicate": False,
                    "duplicateReason": None,
                    "service": "backend",
                    "source": ["keep"],
                    "message": "Keep: Alert message",
                    "description": "Keep: Alert description",
                    "severity": "critical",
                    "pushed": True,
                    "event_id": "1234",
                    "url": "https://www.keephq.dev?alertId=1234",
                    "labels": {"key": "value"},
                    "ticket_url": "https://www.keephq.dev?enrichedTicketId=456",
                    "fingerprint": "1234",
                }
            ]
        }
        use_enum_values = True
        json_encoders = {
            # Converts enums to their values for JSON serialization
            Enum: lambda v: v.value,
        }


class DeleteRequestBody(BaseModel):
    fingerprint: str
    lastReceived: str
    restore: bool = False


class EnrichAlertRequestBody(BaseModel):
    enrichments: dict[str, str]
    fingerprint: str
