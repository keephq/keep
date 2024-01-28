import logging
from enum import Enum
from typing import Any, Dict

from pydantic import AnyHttpUrl, BaseModel, Extra, root_validator, validator

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    CRITICAL = ("critical", 5)
    HIGH = ("high", 4)
    WARNING = ("warning", 3)
    INFO = ("info", 2)
    LOW = ("low", 1)

    def __new__(cls, severity_name, severity_order):
        obj = object.__new__(cls)
        obj._value_ = severity_name
        obj.severity_order = severity_order
        return obj

    @property
    def order(self):
        return self.severity_order

    def __str__(self):
        return self._value_


class AlertStatus(Enum):
    # Active alert
    FIRING = "firing"
    # Alert has been resolved
    RESOLVED = "resolved"
    # Alert has been acknowledged but not resolved
    ACKNOWLEDGED = "acknowledged"
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
    usedApiKey: bool = False
    message: str | None = None
    description: str | None = None
    pushed: bool = False  # Whether the alert was pushed or pulled from the provider
    event_id: str | None = None  # Database alert id
    url: AnyHttpUrl | None = None
    labels: dict | None = {}
    fingerprint: str | None = (
        None  # The fingerprint of the alert (used for alert de-duplication)
    )
    deleted: bool = False  # Whether the alert has been deleted
    assignee: str | None = None  # The assignee of the alert
    providerId: str | None = None  # The provider id
    group: bool = False  # Whether the alert is a group alert

    @validator("fingerprint", pre=True, always=True)
    def assign_fingerprint_if_none(cls, fingerprint, values):
        if fingerprint is None:
            return values.get("name", "")
        return fingerprint

    @validator("deleted", pre=True, always=True)
    def validate_deleted(cls, deleted, values):
        if isinstance(deleted, bool):
            return deleted
        if isinstance(deleted, list):
            return values.get("lastReceived") in deleted

    @root_validator(pre=True)
    def set_default_values(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        # Check and set default severity
        severity = values.get("severity")
        try:
            values["severity"] = AlertSeverity(severity)
        except ValueError:
            logging.warning(
                f"Invalid severity value: {severity}, setting default.",
                extra={"event": values},
            )
            values["severity"] = AlertSeverity.INFO

        # Check and set default status
        status = values.get("status")
        try:
            values["status"] = AlertStatus(status)
        except ValueError:
            logging.warning(
                f"Invalid status value: {status}, setting default.",
                extra={"event": values},
            )
            values["status"] = AlertStatus.FIRING

        values.pop("assignees", None)
        values.pop("deletedAt", None)
        return values

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
