import json
import logging
import math
import os
from typing import Optional
from uuid import UUID

from openai import OpenAI
from pydantic import BaseModel

from keep.api.bl.incidents_bl import IncidentBl
from keep.api.consts import OPENAI_MODEL_NAME
from keep.api.models.db.incident import IncidentStatus
from keep.api.models.incident import IncidentDto


logger = logging.getLogger(__name__)

# Config knobs (so this doesn't become "limit=100 forever" technical debt)
DEFAULT_QUERY_LIMIT = int(os.environ.get("KEEP_INCIDENT_REPORT_QUERY_LIMIT", "100"))
OPENAI_MAX_INCIDENTS = int(os.environ.get("KEEP_INCIDENT_REPORT_OPENAI_LIMIT", "40"))
RECURRING_MAX_CHAIN_DEPTH = int(os.environ.get("KEEP_RECURRING_MAX_CHAIN_DEPTH", "100"))

system_prompt = """
Generate an incident report based on the provided incidents dataset and response schema. Ensure all calculated metrics follow the specified format for consistency.

**Calculations and Metrics:**
1. **Most Frequent Incident Reasons**
   - JSON property name: most_frequent_reasons
   - Identify the most common root causes by analyzing the following fields: incident_name, incident_summary, severity.
   - Try to find root causes that are not explicitly mentioned in the dataset.
   - Be concise, the reasons must be short but descriptive at the same time.
   - Group similar reasons to avoid duplicates.
   - Output only top 6 reasons.
   - Return a JSON object, which is a dictionary.
   - Each key in this dictionary must be an incident reason (a string describing the reason for the incident).
   - The value for each key must be a list of incident IDs (strings) that correspond to that reason.
   - The structure of object in most_frequent_reasons property should follow this exact format:
            {
                "Reason 1": ["incident_id_1", "incident_id_2"],
                "Reason 2": ["incident_id_3"],
                "Reason 3": ["incident_id_4", "incident_id_5", "incident_id_6"]
            }
"""


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


class IncidentReportsBl:
    __open_ai_client = None

    @property
    def open_ai_client(self) -> Optional[OpenAI]:
        if not self.__open_ai_client and os.environ.get("OPENAI_API_KEY"):
            self.__open_ai_client = OpenAI()
        return self.__open_ai_client

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        # NOTE: IncidentBl session mgmt depends on its implementation.
        # If IncidentBl leaks sessions when session=None, that bug is in IncidentBl.
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
        report.recurring_incidents = self.__calculate_recurring_incidents(incidents_dict)
        report.severity_metrics = self.__calculate_severity_metrics(incidents)
        report.services_affected_metrics = self.__calculate_top_services_affected(incidents)

        return report

    def __calculate_report_in_openai(self, incidents: list[IncidentDto]) -> OpenAIReportPart:
        # Correct type return on "no client"
        if self.open_ai_client is None:
            return OpenAIReportPart()

        try:
            # Most recent incidents first
            incidents_sorted = sorted(incidents, key=lambda x: x.creation_time, reverse=True)

            # Limit incidents because OpenAI is slow and token-limited
            incidents_sorted = incidents_sorted[:OPENAI_MAX_INCIDENTS]

            incidents_minified: list[dict] = []
            for item in incidents_sorted:
                incidents_minified.append(
                    {
                        "incident_id": str(item.id),
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
                model=OPENAI_MODEL_NAME,
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

            model_response = response.choices[0].message.content or "{}"

            try:
                return OpenAIReportPart(**json.loads(model_response))
            except Exception as e:
                logger.error(
                    "Failed to parse OpenAI response: %s | Response: %s",
                    e,
                    model_response,
                )
                # Preserve traceback
                raise

        except Exception as e:
            # OpenAI failures should not take down the whole report.
            logger.error("OpenAI report generation failed: %s", e, exc_info=True)
            return OpenAIReportPart()

    def __calculate_top_services_affected(self, incidents: list[IncidentDto]) -> dict[str, int]:
        top_services_affected: dict[str, int] = {}
        for incident in incidents:
            for service in (incident.services or []):
                if service is None:
                    continue
                if isinstance(service, str):
                    s = service.strip()
                    if not s or s.lower() == "null":
                        continue
                    service_key = s
                else:
                    # Defensive: if it isn't a string, stringify it
                    service_key = str(service)

                top_services_affected[service_key] = top_services_affected.get(service_key, 0) + 1

        return top_services_affected

    def __calculate_severity_metrics(self, incidents: list[IncidentDto]) -> dict[str, list[IncidentReportDto]]:
        severity_metrics: dict[str, list[IncidentReportDto]] = {}
        for incident in incidents:
            sev = incident.severity or "unknown"
            severity_metrics.setdefault(sev, []).append(
                IncidentReportDto(
                    incident_name=incident.user_generated_name or incident.ai_generated_name,
                    incident_id=str(incident.id),
                )
            )
        return severity_metrics

    def __calculate_mttd(self, incidents: list[IncidentDto]) -> int:
        duration_sum = 0.0
        incidents_count = 0

        for incident in incidents:
            if not incident.start_time:
                continue
            duration_sum += (incident.creation_time - incident.start_time).total_seconds()
            incidents_count += 1

        if incidents_count == 0:
            return 0

        return math.ceil(duration_sum / incidents_count)

    def __calculate_mttr(self, resolved_incidents: list[IncidentDto]) -> int:
        filtered_incidents = [i for i in resolved_incidents if i.end_time]

        if len(filtered_incidents) == 0:
            return 0

        duration_sum = 0.0
        for incident in filtered_incidents:
            start_time = incident.start_time or incident.creation_time
            duration_sum += (incident.end_time - start_time).total_seconds()

        return math.ceil(duration_sum / len(filtered_incidents))

    def __calculate_durations(self, resolved_incidents: list[IncidentDto]) -> Optional[IncidentDurations]:
        if len(resolved_incidents) == 0:
            return None

        shortest_duration_s: Optional[float] = None
        shortest_id: Optional[UUID] = None
        longest_duration_s: Optional[float] = None
        longest_id: Optional[UUID] = None

        for incident in resolved_incidents:
            start_time = incident.start_time or incident.creation_time
            if not start_time or not incident.end_time:
                continue

            duration = (incident.end_time - start_time).total_seconds()

            if shortest_duration_s is None or duration < shortest_duration_s:
                shortest_duration_s = duration
                shortest_id = incident.id

            if longest_duration_s is None or duration > longest_duration_s:
                longest_duration_s = duration
                longest_id = incident.id

        # If none had valid durations
        if shortest_duration_s is None or longest_duration_s is None:
            return None

        return IncidentDurations(
            shortest_duration_seconds=int(shortest_duration_s),
            shortest_duration_incident_id=str(shortest_id) if shortest_id else None,
            longest_duration_seconds=int(longest_duration_s),
            longest_duration_incident_id=str(longest_id) if longest_id else None,
        )

    def __calculate_recurring_incidents(
        self, incidents_dict: dict[UUID, IncidentDto]
    ) -> list[ReoccuringIncidentReportDto]:
        """
        Walk each incident's same_incident_in_the_past_id chain to find a root.
        Adds cycle detection + max depth guardrail.
        """
        recurring_map: dict[UUID, set[UUID]] = {}

        for incident in incidents_dict.values():
            current_id = incident.same_incident_in_the_past_id
            path: list[UUID] = [incident.id]
            visited: set[UUID] = set(path)

            depth = 0
            while current_id:
                depth += 1
                if depth > RECURRING_MAX_CHAIN_DEPTH:
                    logger.warning("Recurring chain exceeded max depth: %s", path)
                    break

                if current_id in visited:
                    logger.warning("Circular recurring chain detected: %s -> %s", path, current_id)
                    break

                visited.add(current_id)
                path.append(current_id)

                past_incident = incidents_dict.get(current_id)
                if not past_incident:
                    break

                next_id = past_incident.same_incident_in_the_past_id
                if not next_id:
                    # current_id is the root
                    root_id = current_id
                    recurring_map.setdefault(root_id, set()).update(path)
                    break

                current_id = next_id

        results: list[ReoccuringIncidentReportDto] = []
        for root_id, incident_set in recurring_map.items():
            root_incident = incidents_dict.get(root_id)
            if not root_incident:
                # Root missing (deleted/filtered). Skip instead of KeyError.
                continue

            results.append(
                ReoccuringIncidentReportDto(
                    incident_name=root_incident.user_generated_name or root_incident.ai_generated_name,
                    incident_id=str(root_id),
                    occurrence_count=len(incident_set),  # FIXED: count occurrences for that root
                )
            )

        # Optional: sort by most frequent
        results.sort(key=lambda r: r.occurrence_count or 0, reverse=True)
        return results

    def __get_incidents(self, incidents_query_cel: str, allowed_incident_ids: list[str]) -> list[IncidentDto]:
        """
        WARNING: CEL is interpolated. Real fix is to not accept raw CEL from untrusted sources.
        This adds a basic guardrail against obviously sketchy CEL payloads.
        """
        # Lightweight CEL “sanity check” to reduce foot-guns.
        # If incidents_query_cel is internal-only, this is harmless; if user-provided, it’s necessary.
        banned_tokens = [";", "||", "&&&&", "__", "import", "lambda", "eval", "exec"]
        for tok in banned_tokens:
            if tok in incidents_query_cel:
                raise ValueError("Invalid incidents_query_cel")

        query_result = self.incidents_bl.query_incidents(
            tenant_id=self.tenant_id,
            cel=f"status != 'deleted' && {incidents_query_cel}",
            limit=DEFAULT_QUERY_LIMIT,
            offset=0,
            allowed_incident_ids=allowed_incident_ids,
            is_candidate=False,
        )
        return query_result.items