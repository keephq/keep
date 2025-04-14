import datetime
import json
import logging
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Extra, Field, PrivateAttr, root_validator
from sqlmodel import col, desc

from keep.api.models.db.incident import Incident, IncidentSeverity, IncidentStatus
from keep.api.models.db.rule import ResolveOn, Rule


class IncidentStatusChangeDto(BaseModel):
    status: IncidentStatus
    comment: str | None


class IncidentSeverityChangeDto(BaseModel):
    severity: IncidentSeverity
    comment: str | None


class IncidentDtoIn(BaseModel):
    user_generated_name: str | None
    assignee: str | None
    user_summary: str | None
    same_incident_in_the_past_id: UUID | None
    severity: IncidentSeverity | None

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
    status: IncidentStatus = IncidentStatus.FIRING
    assignee: str | None
    services: list[str]

    is_predicted: bool
    is_candidate: bool

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

    enrichments: dict | None = {}
    incident_type: str | None
    incident_application: str | None

    resolve_on: str = Field(
        default=ResolveOn.ALL.value,
        description="Resolution strategy for the incident",
    )

    rule_id: UUID | None
    rule_name: str | None
    rule_is_deleted: bool | None

    _tenant_id: str = PrivateAttr()
    # AlertDto, not explicitly typed because of circular dependency
    _alerts: Optional[List] = PrivateAttr(default=None)

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
    def alerts(self) -> List:
        if self._alerts is not None:
            return self._alerts

        from keep.api.core.db import get_incident_alerts_by_incident_id
        from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts

        try:
            if not self._tenant_id:
                return []
        except Exception:
            logging.getLogger(__name__).error(
                "Tenant ID is not set in incident",
                extra={"incident_id": self.id},
            )
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
            logging.getLogger(__name__).warning(
                f"Invalid status value: {status}, setting default.",
                extra={"event": values},
            )
            values["status"] = IncidentStatus.FIRING
        return values

    @classmethod
    def from_db_incident(cls, db_incident: "Incident", rule: "Rule" = None):

        severity = (
            IncidentSeverity.from_number(db_incident.severity)
            if isinstance(db_incident.severity, int)
            else db_incident.severity
        )

        # some default value for resolve_on
        if not db_incident.resolve_on:
            db_incident.resolve_on = ResolveOn.ALL.value

        dto = cls(
            id=db_incident.id,
            user_generated_name=db_incident.user_generated_name,
            ai_generated_name=db_incident.ai_generated_name,
            user_summary=db_incident.user_summary,
            generated_summary=db_incident.generated_summary,
            is_predicted=db_incident.is_predicted,
            is_candidate=db_incident.is_candidate,
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
            fingerprint=db_incident.fingerprint,
            same_incident_in_the_past_id=db_incident.same_incident_in_the_past_id,
            merged_into_incident_id=db_incident.merged_into_incident_id,
            merged_by=db_incident.merged_by,
            merged_at=db_incident.merged_at,
            incident_type=db_incident.incident_type,
            incident_application=str(db_incident.incident_application),
            enrichments=db_incident.enrichments,
            resolve_on=db_incident.resolve_on,
            rule_id=rule.id if rule else None,
            rule_name=rule.name if rule else None,
            rule_is_deleted=rule.is_deleted if rule else None,
        )

        # This field is required for getting alerts when required
        dto._tenant_id = db_incident.tenant_id

        if db_incident.enrichments:
            dto = dto.copy(update=db_incident.enrichments)

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
            is_candidate=self.is_candidate,
            rule_fingerprint=self.rule_fingerprint,
            fingerprint=self.fingerprint,
            same_incident_in_the_past_id=self.same_incident_in_the_past_id,
            merged_into_incident_id=self.merged_into_incident_id,
            merged_by=self.merged_by,
            merged_at=self.merged_at,
        )

        return db_incident


class SplitIncidentRequestDto(BaseModel):
    alert_fingerprints: list[str]
    destination_incident_id: UUID


class SplitIncidentResponseDto(BaseModel):
    destination_incident_id: UUID
    moved_alert_fingerprints: list[str]


class MergeIncidentsRequestDto(BaseModel):
    source_incident_ids: list[UUID]
    destination_incident_id: UUID


class MergeIncidentsResponseDto(BaseModel):
    merged_incident_ids: list[UUID]
    failed_incident_ids: list[UUID]
    destination_incident_id: UUID
    message: str


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
