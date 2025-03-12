import json
import os
from uuid import UUID
from openai import OpenAI
from pydantic import BaseModel
from keep.api.bl.incidents_bl import IncidentBl
from typing import Optional
import logging
import math

from keep.api.models.db.incident import IncidentStatus
from keep.api.models.incident import IncidentDto

class IncidentMetrics(BaseModel):
    total_incidents: Optional[int] = None
    resolved_incidents: Optional[int] = None
    deleted_incidents: Optional[int] = None
    unresolved_incidents: Optional[int] = None


class IncidentDurations(BaseModel):
    shortest_duration_seconds: Optional[int] = None
    shortest_duration_incident_id: Optional[str] = None
    longest_duration_seconds: Optional[int] = None
    longest_duration_incident_id: Optional[str] = None


class IncidentReportDto(BaseModel):
    incident_name: Optional[str] = None
    incident_id: Optional[str] = None


class ReoccuringIncidentReportDto(IncidentReportDto):
    occurrence_count: Optional[int] = None


class IncidentReport(BaseModel):
    services_affected_metrics: Optional[dict[str, int]] = None
    severity_metrics: Optional[dict[str, list[IncidentReportDto]]] = None
    incident_durations: Optional[IncidentDurations] = None
    mean_time_to_detect_seconds: Optional[int] = None
    mean_time_to_resolve_seconds: Optional[int] = None
    most_frequent_reasons: Optional[dict[str, list[str]]] = None
    recurring_incidents: Optional[list[ReoccuringIncidentReportDto]] = None


class OpenAIReportPart(BaseModel):
    most_frequent_reasons: Optional[dict[str, list[str]]] = None


system_prompt = """
Generate an incident report based on the provided incidents dataset and response schema. Ensure all calculated metrics follow the specified format for consistency.

**Calculations and Metrics:**
1. **Most Frequent Incident Reasons**
   - Identify the most common root causes by analyzing the following fields: incident_name, incident_summary, severity.
   - Try to find root causes that are not explicitly mentioned in the dataset.
   - Group similar reasons to avoid duplicates.
   - Output `most_frequent_reasons` as a dictionary with reason as key and list of incident ids as value whose reason it is.
"""

logger = logging.getLogger(__name__)

class IncidentReportsBl:
    __open_ai_client = None

    @property
    def open_ai_client(self):
        if not self.__open_ai_client and os.environ.get("OPENAI_API_KEY"):
            self.__open_ai_client = OpenAI()

        return self.__open_ai_client

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.incidents_bl = IncidentBl(
            tenant_id=tenant_id, session=None, pusher_client=None, user=None
        )

    def get_incident_reports(
        self, incidents_query_cel: str, allowed_incident_ids: list[str]
    ) -> IncidentReport:
        incidents = self.__get_incidents(incidents_query_cel, allowed_incident_ids)
        open_ai_report_part = self.__calculate_report_in_openai(incidents)
        report = IncidentReport(
            most_frequent_reasons=open_ai_report_part.most_frequent_reasons
        )
        incidents_dict = {incident.id: incident for incident in incidents}
        resolved_incidents = [
            incident
            for incident in incidents
            if incident.status == IncidentStatus.RESOLVED
        ]
        report.mean_time_to_detect_seconds = self.__calculate_mttd(incidents)
        report.mean_time_to_resolve_seconds = self.__calculate_mttr(resolved_incidents)
        report.incident_durations = self.__calculate_durations(resolved_incidents)
        report.recurring_incidents = self.__calculate_recurring_incidents(
            incidents_dict
        )
        report.severity_metrics = self.__calculate_severity_metrics(incidents)
        report.services_affected_metrics = self.__calculate_top_services_affected(
            incidents
        )

        return report

    def __calculate_report_in_openai(
        self, incidents: list[IncidentDto]
    ) -> OpenAIReportPart:
        if self.open_ai_client is None:
            return IncidentReport()

        incidents_minified: list[dict] = []
        for item in incidents:
            incidents_minified.append(
                {
                    "incident_name": "\n".join(
                        filter(None, [item.user_generated_name, item.ai_generated_name])
                    ),
                    "incident_summary": "\n".join(
                        filter(None, [item.user_summary, item.generated_summary])
                    ),
                    "severity": item.severity,
                    "services": item.services,
                }
            )

        incidents_json = json.dumps(incidents_minified, default=str)

        response = self.open_ai_client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": incidents_json},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "OpenAIReportPart",
                    "schema": OpenAIReportPart.schema(),
                },
            },
            seed=1239,
            temperature=0.2,
        )

        model_response = response.choices[0].message.content
        report = OpenAIReportPart(**json.loads(model_response))
        return report

    def __calculate_top_services_affected(
        self, incidents: list[IncidentDto]
    ) -> dict[str, int]:
        top_services_affected = {}
        for incident in incidents:
            for service in incident.services:
                if service == "null":
                    continue
                if service not in top_services_affected:
                    top_services_affected[service] = 0
                top_services_affected[service] += 1

        return top_services_affected

    def __calculate_severity_metrics(
        self, incidents: list[IncidentDto]
    ) -> dict[str, list[IncidentReportDto]]:
        severity_metrics = {}
        for incident in incidents:
            if incident.severity not in severity_metrics:
                severity_metrics[incident.severity] = []
            severity_metrics[incident.severity].append(
                IncidentReportDto(
                    incident_name=incident.user_generated_name
                    or incident.ai_generated_name,
                    incident_id=str(incident.id),
                )
            )

        return severity_metrics

    def __calculate_mttd(self, incidents: list[IncidentDto]) -> int:
        duration_sum = 0
        incidents_count = 0

        for incident in incidents:
            if not incident.start_time:
                continue

            duration_sum += (
                incident.creation_time - incident.start_time
            ).total_seconds()
            incidents_count += 1

        if incidents_count == 0:
            return 0

        return math.ceil(duration_sum / incidents_count)

    def __calculate_mttr(self, resolved_incidents: list[IncidentDto]) -> int:
        filtered_incidents = [
            incident for incident in resolved_incidents if incident.end_time
        ]

        if len(filtered_incidents) == 0:
            return 0

        duration_sum = 0
        for incident in filtered_incidents:
            start_time = incident.start_time or incident.creation_time
            duration_sum += (incident.end_time - start_time).total_seconds()

        return math.ceil(duration_sum / len(filtered_incidents))

    def __calculate_durations(
        self, resolved_incidents: list[IncidentDto]
    ) -> IncidentDurations:
        if len(resolved_incidents) == 0:
            return None

        shortest_duration_ms = None
        shortest_duration_incident_id = None
        longest_duration_ms = None
        longest_duration_incident_id = None

        for incident in resolved_incidents:
            start_time = incident.start_time or incident.creation_time
            if not start_time or not incident.end_time:
                continue

            duration = (incident.end_time - start_time).total_seconds()
            if not shortest_duration_ms or duration < shortest_duration_ms:
                shortest_duration_ms = duration
                shortest_duration_incident_id = incident.id

            if not longest_duration_ms or duration > longest_duration_ms:
                longest_duration_ms = duration
                longest_duration_incident_id = incident.id

        return IncidentDurations(
            shortest_duration_seconds=shortest_duration_ms,
            shortest_duration_incident_id=str(shortest_duration_incident_id),
            longest_duration_seconds=longest_duration_ms,
            longest_duration_incident_id=str(longest_duration_incident_id),
        )

    def __calculate_recurring_incidents(
        self, incidents_dict: dict[UUID, IncidentDto]
    ) -> list[ReoccuringIncidentReportDto]:
        recurring_incidents: dict[str, set[str]] = {}
        for incident in incidents_dict.values():
            current_incident_in_the_past_id = incident.same_incident_in_the_past_id
            path = list([incident.id])
            while current_incident_in_the_past_id:
                path.append(current_incident_in_the_past_id)
                past_incident = same_incident_in_the_past_id = incidents_dict.get(
                    current_incident_in_the_past_id, None
                )

                if not past_incident:
                    break

                same_incident_in_the_past_id = (
                    past_incident.same_incident_in_the_past_id
                )

                if not same_incident_in_the_past_id:
                    root_incident_id = path[-1]

                    if root_incident_id not in recurring_incidents:
                        recurring_incidents[root_incident_id] = set()

                    for incident_id in path:
                        recurring_incidents[root_incident_id].add(incident_id)
                    break

                current_incident_in_the_past_id = (
                    past_incident.same_incident_in_the_past_id
                )

        return [
            ReoccuringIncidentReportDto(
                incident_name=incidents_dict[root_incident_id].user_generated_name
                or incidents_dict[root_incident_id].ai_generated_name,
                incident_id=str(root_incident_id),
                occurrence_count=len(recurring_incidents),
            )
            for root_incident_id, recurring_incidents in recurring_incidents.items()
        ]

    def __get_incidents(
        self, incidents_query_cel: str, allowed_incident_ids: list[str]
    ) -> list[IncidentDto]:
        query_result = self.incidents_bl.query_incidents(
            tenant_id=self.tenant_id,
            cel=f"status != 'deleted' && {incidents_query_cel}",
            limit=100,
            offset=0,
            allowed_incident_ids=allowed_incident_ids,
            is_confirmed=True,
        )
        return query_result.items
