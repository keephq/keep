import datetime
import hashlib
import json
import logging
import uuid
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

import pytz
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    Extra,
    Field,
    PrivateAttr,
    root_validator,
    validator,
)
from sqlalchemy import desc
from sqlmodel import col

if TYPE_CHECKING:
    from keep.api.models.db.alert import Incident

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


class SeverityBaseInterface(Enum):
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

    @classmethod
    def from_number(cls, n):
        for severity in cls:
            if severity.order == n:
                return severity
        raise ValueError(f"No AlertSeverity with order {n}")

    def __lt__(self, other):
        if isinstance(other, SeverityBaseInterface):
            return self.order < other.order
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, SeverityBaseInterface):
            return self.order <= other.order
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, SeverityBaseInterface):
            return self.order > other.order
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, SeverityBaseInterface):
            return self.order >= other.order
        return NotImplemented


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


class IncidentStatus(Enum):
    # Active incident
    FIRING = "firing"
    # Incident has been resolved
    RESOLVED = "resolved"
    # Incident has been acknowledged but not resolved
    ACKNOWLEDGED = "acknowledged"
    # Incident was merged with another incident
    MERGED = "merged"


class IncidentSeverity(SeverityBaseInterface):
    CRITICAL = ("critical", 5)
    HIGH = ("high", 4)
    WARNING = ("warning", 3)
    INFO = ("info", 2)
    LOW = ("low", 1)


class AlertDto(BaseModel):
    id: str | None
    name: str
    status: AlertStatus
    severity: AlertSeverity
    lastReceived: str
    firingStartTime: str | None = None
    environment: str = "undefined"
    isFullDuplicate: bool | None = False
    isPartialDuplicate: bool | None = False
    duplicateReason: str | None = None
    service: str | None = None
    source: list[str] | None = []
    apiKeyRef: str | None = None
    message: str | None = None
    description: str | None = None
    pushed: bool = False  # Whether the alert was pushed or pulled from the provider
    event_id: str | None = None  # Database alert id
    url: AnyHttpUrl | None = None
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

        if not last_received:
            return datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Try to convert the date to iso format
        # see: https://github.com/keephq/keep/issues/1397
        if convert_to_iso_format(last_received):
            return convert_to_iso_format(last_received)

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
        if values.get("dismissed"):
            values["status"] = AlertStatus.SUPPRESSED
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


class EnrichAlertRequestBody(BaseModel):
    enrichments: dict[str, str]
    fingerprint: str


class UnEnrichAlertRequestBody(BaseModel):
    enrichments: list[str]
    fingerprint: str


class IncidentDtoIn(BaseModel):
    user_generated_name: str | None
    assignee: str | None
    user_summary: str | None
    same_incident_in_the_past_id: UUID | None

    class Config:
        extra = Extra.allow
        schema_extra = {
            "examples": [
                {
                    "id": "c2509cb3-6168-4347-b83b-a41da9df2d5b",
                    "name": "Incident name",
                    "user_summary": "Keep: Incident description",
                    "status": "firing",
                }
            ]
        }


class IncidentDto(IncidentDtoIn):
    id: UUID

    start_time: datetime.datetime | None
    last_seen_time: datetime.datetime | None
    end_time: datetime.datetime | None
    creation_time: datetime.datetime | None

    alerts_count: int
    alert_sources: list[str]
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.FIRING
    assignee: str | None
    services: list[str]

    is_predicted: bool
    is_confirmed: bool

    generated_summary: str | None
    ai_generated_name: str | None

    rule_fingerprint: str | None
    fingerprint: (
        str | None
    )  # This is the fingerprint of the incident generated by the underlying tool

    same_incident_in_the_past_id: UUID | None

    merged_into_incident_id: UUID | None
    merged_by: str | None
    merged_at: datetime.datetime | None

    _tenant_id: str = PrivateAttr()
    _alerts: Optional[List[AlertDto]] = PrivateAttr(default=None)

    def __init__(self, **data):
        super().__init__(**data)
        if "alerts" in data:
            self._alerts = data["alerts"]

    def __str__(self) -> str:
        # Convert the model instance to a dictionary
        model_dict = self.dict()
        return json.dumps(model_dict, indent=4, default=str)

    class Config:
        extra = Extra.allow
        schema_extra = IncidentDtoIn.Config.schema_extra
        underscore_attrs_are_private = True

        json_encoders = {
            # Converts UUID to their values for JSON serialization
            UUID: lambda v: str(v),
        }

    @property
    def name(self):
        return self.user_generated_name or self.ai_generated_name

    @property
    def alerts(self) -> List["AlertDto"]:
        if self._alerts is not None:
            return self._alerts

        from keep.api.core.db import get_incident_alerts_by_incident_id
        from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts

        if not self._tenant_id:
            return []
        alerts, _ = get_incident_alerts_by_incident_id(self._tenant_id, str(self.id))
        return convert_db_alerts_to_dto_alerts(alerts)

    @root_validator(pre=True)
    def set_default_values(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        # Check and set default status
        status = values.get("status")
        try:
            values["status"] = IncidentStatus(status)
        except ValueError:
            logging.warning(
                f"Invalid status value: {status}, setting default.",
                extra={"event": values},
            )
            values["status"] = IncidentStatus.FIRING
        return values

    @classmethod
    def from_db_incident(cls, db_incident: "Incident"):

        severity = (
            IncidentSeverity.from_number(db_incident.severity)
            if isinstance(db_incident.severity, int)
            else db_incident.severity
        )

        dto = cls(
            id=db_incident.id,
            user_generated_name=db_incident.user_generated_name,
            ai_generated_name=db_incident.ai_generated_name,
            user_summary=db_incident.user_summary,
            generated_summary=db_incident.generated_summary,
            is_predicted=db_incident.is_predicted,
            is_confirmed=db_incident.is_confirmed,
            creation_time=db_incident.creation_time,
            start_time=db_incident.start_time,
            last_seen_time=db_incident.last_seen_time,
            end_time=db_incident.end_time,
            alerts_count=db_incident.alerts_count,
            alert_sources=db_incident.sources or [],
            severity=severity,
            status=db_incident.status,
            assignee=db_incident.assignee,
            services=db_incident.affected_services or [],
            rule_fingerprint=db_incident.rule_fingerprint,
            same_incident_in_the_past_id=db_incident.same_incident_in_the_past_id,
            merged_into_incident_id=db_incident.merged_into_incident_id,
            merged_by=db_incident.merged_by,
            merged_at=db_incident.merged_at,
        )

        # This field is required for getting alerts when required
        dto._tenant_id = db_incident.tenant_id
        return dto

    def to_db_incident(self) -> "Incident":
        """Converts an IncidentDto instance to an Incident database model."""
        from keep.api.models.db.alert import Incident

        db_incident = Incident(
            id=self.id,
            user_generated_name=self.user_generated_name,
            ai_generated_name=self.ai_generated_name,
            user_summary=self.user_summary,
            generated_summary=self.generated_summary,
            assignee=self.assignee,
            severity=self.severity.order,
            status=self.status.value,
            creation_time=self.creation_time or datetime.datetime.utcnow(),
            start_time=self.start_time,
            end_time=self.end_time,
            last_seen_time=self.last_seen_time,
            alerts_count=self.alerts_count,
            affected_services=self.services,
            sources=self.alert_sources,
            is_predicted=self.is_predicted,
            is_confirmed=self.is_confirmed,
            rule_fingerprint=self.rule_fingerprint,
            same_incident_in_the_past_id=self.same_incident_in_the_past_id,
            merged_into_incident_id=self.merged_into_incident_id,
            merged_by=self.merged_by,
            merged_at=self.merged_at,
        )

        return db_incident


class MergeIncidentsRequestDto(BaseModel):
    source_incident_ids: list[UUID]
    destination_incident_id: UUID


class MergeIncidentsResponseDto(BaseModel):
    merged_incident_ids: list[UUID]
    skipped_incident_ids: list[UUID]
    failed_incident_ids: list[UUID]
    destination_incident_id: UUID
    message: str


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


class DeduplicationRuleRequestDto(BaseModel):
    name: str
    description: Optional[str] = None
    provider_type: str
    provider_id: Optional[str] = None
    fingerprint_fields: list[str]
    full_deduplication: bool = False
    ignore_fields: Optional[list[str]] = None


class IncidentStatusChangeDto(BaseModel):
    status: IncidentStatus
    comment: str | None


class IncidentSorting(Enum):
    creation_time = "creation_time"
    start_time = "start_time"
    last_seen_time = "last_seen_time"
    severity = "severity"
    status = "status"
    alerts_count = "alerts_count"

    creation_time_desc = "-creation_time"
    start_time_desc = "-start_time"
    last_seen_time_desc = "-last_seen_time"
    severity_desc = "-severity"
    status_desc = "-status"
    alerts_count_desc = "-alerts_count"

    def get_order_by(self, model):
        if self.value.startswith("-"):
            return desc(col(getattr(model, self.value[1:])))

        return col(getattr(model, self.value))


class IncidentListFilterParamsDto(BaseModel):
    statuses: List[IncidentStatus] = [s.value for s in IncidentStatus]
    severities: List[IncidentSeverity] = [s.value for s in IncidentSeverity]
    assignees: List[str]
    services: List[str]
    sources: List[str]


class IncidentCandidate(BaseModel):
    incident_name: str
    alerts: List[int] = Field(
        description="List of alert numbers (1-based index) included in this incident"
    )
    reasoning: str
    severity: str = Field(
        description="Assessed severity level",
        enum=["Low", "Medium", "High", "Critical"],
    )
    recommended_actions: List[str]
    confidence_score: float = Field(
        description="Confidence score of the incident clustering (0.0 to 1.0)"
    )
    confidence_explanation: str = Field(
        description="Explanation of how the confidence score was calculated"
    )


class IncidentClustering(BaseModel):
    incidents: List[IncidentCandidate]


class IncidentCommit(BaseModel):
    accepted: bool
    original_suggestion: dict
    changes: dict = Field(default_factory=dict)
    incident: IncidentDto


class IncidentsClusteringSuggestion(BaseModel):
    incident_suggestion: list[IncidentDto]
    suggestion_id: str
