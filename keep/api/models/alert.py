import datetime
import hashlib
import json
import logging
import uuid
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

import pytz
from pydantic import AnyHttpUrl, BaseModel, Extra, root_validator, validator

from keep.api.models.severity_base import SeverityBaseInterface

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def get_fingerprint(fingerprint, values):
    # if its none, use the name
    if fingerprint is None:
        fingerprint_payload = values.get("name")
        # if the alert name is None, than use the entire payload
        if not fingerprint_payload:
            logger.warning("No name to alert, using the entire payload")
            fingerprint_payload = json.dumps(values)
        fingerprint = hashlib.sha256(fingerprint_payload.encode()).hexdigest()
    # take only the first 255 characters
    else:
        fingerprint = fingerprint[:255]
    return fingerprint


class AlertSeverity(SeverityBaseInterface):
    CRITICAL = ("critical", 5)
    HIGH = ("high", 4)
    WARNING = ("warning", 3)
    INFO = ("info", 2)
    LOW = ("low", 1)


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


class DismissAlertRequest(BaseModel):
    alert_id: Optional[str] = None


class AlertErrorDto(BaseModel):
    id: str
    provider_type: str
    event: dict
    error_message: Optional[str] = None
    timestamp: datetime.datetime


class AlertDto(BaseModel):
    id: str | None
    name: str
    status: AlertStatus
    severity: AlertSeverity
    lastReceived: str
    firingStartTime: str | None = None
    firingCounter: int = 0
    environment: str = "undefined"
    isFullDuplicate: bool | None = False
    isPartialDuplicate: bool | None = False
    duplicateReason: str | None = None
    service: str | None = None
    source: list[str] | None = []
    apiKeyRef: str | None = None
    message: str | None = None
    description: str | None = None
    description_format: str | None = None  # Can be 'markdown' or 'html'
    pushed: bool = False  # Whether the alert was pushed or pulled from the provider
    event_id: str | None = None  # Database alert id
    url: AnyHttpUrl | None = None
    imageUrl: AnyHttpUrl | None = None
    labels: dict | None = {}
    fingerprint: str | None = (
        None  # The fingerprint of the alert (used for alert de-duplication)
    )
    deleted: bool = (
        False  # @tal: Obselete field since we have dismissed, but kept for backwards compatibility
    )
    dismissUntil: str | None = None  # The time until the alert is dismissed
    # DO NOT MOVE DISMISSED ABOVE dismissedUntil since it is used in root_validator
    dismissed: bool = False  # Whether the alert has been dismissed
    assignee: str | None = None  # The assignee of the alert
    providerId: str | None = None  # The provider id
    providerType: str | None = None  # The provider type
    note: str | None = None  # The note of the alert
    startedAt: str | None = (
        None  # The time the alert started - e.g. if alert triggered multiple times, it will be the time of the first trigger (calculated on querying)
    )
    isNoisy: bool = False  # Whether the alert is noisy

    enriched_fields: list = []
    incident: str | None = None

    def __str__(self) -> str:
        # Convert the model instance to a dictionary
        model_dict = self.dict()
        return json.dumps(model_dict, indent=4, default=str)

    def __eq__(self, other):
        if isinstance(other, AlertDto):
            # Convert both instances to dictionaries
            dict_self = self.dict()
            dict_other = other.dict()

            # Fields to exclude from comparison since they are bit different in different db's
            # todo: solve it in a better way
            exclude_fields = {"lastReceived", "startedAt", "event_id"}

            # Remove excluded fields from both dictionaries
            for field in exclude_fields:
                dict_self.pop(field, None)
                dict_other.pop(field, None)

            # Compare the dictionaries
            return dict_self == dict_other
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    @validator("fingerprint", pre=True, always=True)
    def assign_fingerprint_if_none(cls, fingerprint, values):
        return get_fingerprint(fingerprint, values)

    @validator("deleted", pre=True, always=True)
    def validate_deleted(cls, deleted, values):
        if isinstance(deleted, bool):
            return deleted
        if isinstance(deleted, list):
            return values.get("lastReceived") in deleted

    @validator("url", pre=True)
    def prepend_https(cls, url):
        if isinstance(url, str) and not url.startswith("http"):
            # @tb: in some cases we drop the event because of invalid url with no scheme
            # invalid or missing URL scheme (type=value_error.url.scheme)
            return f"https://{url}"
        return url

    @validator("lastReceived", pre=True, always=True)
    def validate_last_received(cls, last_received):
        def convert_to_iso_format(date_string):
            try:
                dt = datetime.datetime.fromisoformat(date_string)
                dt_utc = dt.astimezone(pytz.UTC)
                return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            except ValueError:
                return None

        def parse_unix_timestamp(timestamp_string):
            try:
                # Remove trailing 'Z' if present
                timestamp_string = timestamp_string.rstrip("Z")
                # Convert string to float
                timestamp = float(timestamp_string)
                # Create datetime from timestamp
                dt = datetime.datetime.fromtimestamp(
                    timestamp, tz=datetime.timezone.utc
                )
                return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            except (ValueError, TypeError):
                return None

        if not last_received:
            return datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Try to convert the date to iso format
        # see: https://github.com/keephq/keep/issues/1397
        iso_date = convert_to_iso_format(last_received)
        if iso_date:
            return iso_date

        # Try to parse as UNIX timestamp
        unix_date = parse_unix_timestamp(last_received)
        if unix_date:
            return unix_date

        raise ValueError(f"Invalid date format: {last_received}")

    @validator("dismissed", pre=True, always=True)
    def validate_dismissed(cls, dismissed, values):
        # normzlize dismissed value
        if isinstance(dismissed, str):
            dismissed = dismissed.lower() == "true"

        # if dismissed is False, return False
        if not dismissed:
            return dismissed

        # else, validate dismissedUntil
        dismiss_until = values.get("dismissUntil")
        # if there's no dismissUntil, return just return dismissed
        if not dismiss_until or dismiss_until == "forever":
            return dismissed

        # if there's dismissUntil, validate it
        dismiss_until_datetime = datetime.datetime.strptime(
            dismiss_until, "%Y-%m-%dT%H:%M:%S.%fZ"
        ).replace(tzinfo=datetime.timezone.utc)
        dismissed = (
            datetime.datetime.now(datetime.timezone.utc) < dismiss_until_datetime
        )
        return dismissed

    @validator("description_format")
    def validate_description_format(cls, description_format):
        if description_format is None:
            return None
        valid_formats = ["markdown", "html"]
        if description_format not in valid_formats:
            raise ValueError(f"description_format must be one of {valid_formats}")
        return description_format

    @root_validator(pre=True)
    def set_default_values(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        # Check and set id:
        if not values.get("id"):
            values["id"] = str(uuid.uuid4())

        # Check and set default severity
        severity = values.get("severity")
        try:
            # if severity is int, convert it to AlertSeverity
            if isinstance(severity, int):
                values["severity"] = AlertSeverity.from_number(severity)
            else:
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

        # this is code duplication of enrichment_helpers.py and should be refactored
        lastReceived = values.get("lastReceived", None)
        if not lastReceived:
            lastReceived = datetime.datetime.now(datetime.timezone.utc).isoformat()
            values["lastReceived"] = lastReceived

        assignees = values.pop("assignees", None)
        # In some cases (for example PagerDuty) the assignees is list of dicts and we don't handle it atm.
        if assignees and isinstance(assignees, dict):
            dt = datetime.datetime.fromisoformat(lastReceived)
            dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            assignee = assignees.get(lastReceived) or assignees.get(dt)
            values["assignee"] = assignee
        values.pop("deletedAt", None)
        return values

    # after root_validator to ensure that the values are set
    @root_validator(pre=False)
    def validate_status(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        # if dismissed, change status to SUPPRESSED
        # note this is happen AFTER validate_dismissed which already consider
        #   dismissed + dismissUntil
        # if values.get("dismissed"):
        #     values["status"] = AlertStatus.SUPPRESSED
        return values

    class Config:
        extra = Extra.allow
        schema_extra = {
            "examples": [
                {
                    "id": "1234",
                    "name": "Pod 'api-service-production' lacks memory",
                    "status": "firing",
                    "lastReceived": "2021-01-01T00:00:00.000Z",
                    "environment": "production",
                    "duplicateReason": None,
                    "service": "backend",
                    "source": ["prometheus"],
                    "message": "The pod 'api-service-production' lacks memory causing high error rate",
                    "description": "Due to the lack of memory, the pod 'api-service-production' is experiencing high error rate",
                    "description_format": "markdown",
                    "severity": "critical",
                    "pushed": True,
                    "url": "https://www.keephq.dev?alertId=1234",
                    "labels": {
                        "pod": "api-service-production",
                        "region": "us-east-1",
                        "cpu": "88",
                        "memory": "100Mi",
                    },
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


class AlertWithIncidentLinkMetadataDto(AlertDto):
    is_created_by_ai: bool = False

    @classmethod
    def from_db_instance(cls, db_alert, db_alert_to_incident):
        return cls(
            is_created_by_ai=db_alert_to_incident.is_created_by_ai,
            **db_alert.event,
        )


class DeleteRequestBody(BaseModel):
    fingerprint: str
    lastReceived: str
    restore: bool = False


class DismissRequestBody(BaseModel):
    fingerprint: str
    dismissUntil: str
    dismissComment: str
    restore: bool = False


class EnrichAlertNoteRequestBody(BaseModel):
    note: str
    fingerprint: str


class EnrichAlertRequestBody(BaseModel):
    enrichments: dict[str, str]
    fingerprint: str


class BatchEnrichAlertRequestBody(BaseModel):
    enrichments: dict[str, str]
    fingerprints: list[str]


class UnEnrichAlertRequestBody(BaseModel):
    enrichments: list[str]
    fingerprint: str


class DeduplicationRuleDto(BaseModel):
    id: str | None  # UUID
    name: str
    description: str
    default: bool
    distribution: list[dict]  # list of {hour: int, count: int}
    provider_id: str | None  # None for default rules
    provider_type: str
    last_updated: str | None
    last_updated_by: str | None
    created_at: str | None
    created_by: str | None
    ingested: int
    dedup_ratio: float
    enabled: bool
    fingerprint_fields: list[str]
    full_deduplication: bool
    ignore_fields: list[str]
    is_provisioned: bool


class DeduplicationRuleRequestDto(BaseModel):
    name: str
    description: Optional[str] = None
    provider_type: str
    provider_id: Optional[str] = None
    fingerprint_fields: list[str]
    full_deduplication: bool = False
    ignore_fields: Optional[list[str]] = None


class EnrichIncidentRequestBody(BaseModel):
    enrichments: Dict[str, Any]
    force: bool = False
