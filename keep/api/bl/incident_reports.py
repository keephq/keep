import json
from openai import OpenAI
from pydantic import BaseModel
from keep.api.bl.incidents_bl import IncidentBl


class IncidentMetrics(BaseModel):
    total_incidents: int
    resolved_incidents: int
    deleted_incidents: int
    unresolved_incidents: int


class IncidentDurations(BaseModel):
    shortest_duration_ms: int
    shortest_duration_incident_id: str
    longest_duration_ms: int
    longest_duration_incident_id: str


class TimeBasedMetrics(BaseModel):
    incidents_in_january_2025: int
    incidents_in_february_2025: int
    peak_incident_date: str
    peak_incident_count: int


class IncidentReport(BaseModel):
    incident_metrics: IncidentMetrics
    top_services_affected: list[str]
    common_incident_names: list[str]
    severity_metrics: dict[str, int]
    incident_durations: IncidentDurations
    time_based_metrics: TimeBasedMetrics


system_prompt = """

"""


class IncidentReports:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.incidents_bl = IncidentBl(
            tenant_id=tenant_id, session=None, pusher_client=None, user=None
        )
        self.open_ai_client = OpenAI()

    def get_incident_reports(
        self, incidents_query_cel: str, allowed_incident_ids: list[str]
    ) -> IncidentReport:
        query_result = self.incidents_bl.query_incidents(
            tenant_id=self.tenant_id,
            cel=incidents_query_cel,
            limit=100,
            offset=0,
            allowed_incident_ids=allowed_incident_ids,
            is_confirmed=True,
        )
        incidents_json = json.dumps([item.dict() for item in query_result.items])

        print("f")
