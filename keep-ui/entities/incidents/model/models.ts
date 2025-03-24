// TODO: refactor, move to entities
import { AlertDto } from "@/entities/alerts/model";

export enum Status {
  Firing = "firing",
  Resolved = "resolved",
  Acknowledged = "acknowledged",
  Merged = "merged",
  Deleted = "deleted",
}

export enum Severity {
  Critical = "critical",
  High = "high",
  Warning = "warning",
  Low = "low",
  Info = "info",
}

export const DefaultIncidentFilteredStatuses: string[] = [
  Status.Firing,
  Status.Acknowledged,
  Status.Merged,
];
export const DefaultIncidentFilters: object = {
  status: DefaultIncidentFilteredStatuses,
};

// on initial page load, we have to display only active incidents
export const DEFAULT_INCIDENTS_CEL =
  "is_candidate == false && !(status in ['resolved', 'deleted', 'merged'])";
export const DEFAULT_INCIDENTS_UNCHECKED_OPTIONS = [
  "resolved",
  "deleted",
  "merged",
];
export const DEFAULT_INCIDENTS_SORTING = { id: "creation_time", desc: true };
export const DEFAULT_INCIDENTS_PAGE_SIZE = 20;
export const INCIDENT_PAGINATION_OPTIONS = [
  { value: "10", label: "10" },
  { value: "20", label: "20" },
  { value: "50", label: "50" },
  { value: "100", label: "100" },
];

export interface IncidentDto {
  id: string;
  user_generated_name: string;
  ai_generated_name: string;
  user_summary: string;
  generated_summary: string;
  assignee: string;
  severity: Severity;
  status: Status;
  alerts_count: number;
  alert_sources: string[];
  services: string[];
  start_time?: Date;
  last_seen_time?: Date;
  end_time?: Date;
  creation_time: Date;
  is_candidate: boolean;
  rule_fingerprint: string;
  same_incident_in_the_past_id: string;
  following_incidents_ids: string[];
  merged_into_incident_id: string;
  merged_by: string;
  merged_at: Date;
  fingerprint: string;
  enrichments: { [key: string]: any };
  incident_type?: string;
  incident_application?: string;
  resolve_on: "all_resolved" | "first" | "last" | "never";
  rule_id?: string;
  rule_name?: string;
  rule_is_deleted?: boolean;
}

export interface IncidentCandidateDto {
  id: string;
  name: string;
  description: string;
  description_format?: "markdown" | "html" | null;
  severity: string;
  confidence_score: number;
  confidence_explanation: string;
  alerts: AlertDto[];
}

export interface PaginatedIncidentsDto {
  limit: number;
  offset: number;
  count: number;
  items: IncidentDto[];
}

export interface PaginatedIncidentAlertsDto {
  limit: number;
  offset: number;
  count: number;
  items: AlertDto[];
}

export interface IncidentsMetaDto {
  statuses: string[];
  severities: string[];
  assignees: string[];
  services: string[];
  sources: string[];
}
