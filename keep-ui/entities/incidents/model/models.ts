// TODO: refactor, move to entities
import { AlertDto } from "@/entities/alerts/model";

export enum Status {
  Firing = "firing",
  Resolved = "resolved",
  Acknowledged = "acknowledged",
  Merged = "merged",
  Deleted = "deleted",
}

export const DefaultIncidentFilteredStatuses: string[] = [
  Status.Firing,
  Status.Acknowledged,
  Status.Merged,
];
export const DefaultIncidentFilters: object = {
  status: DefaultIncidentFilteredStatuses,
};

export interface IncidentDto {
  id: string;
  user_generated_name: string;
  ai_generated_name: string;
  user_summary: string;
  generated_summary: string;
  assignee: string;
  severity: string;
  status: Status;
  alerts_count: number;
  alert_sources: string[];
  services: string[];
  start_time?: Date;
  last_seen_time?: Date;
  end_time?: Date;
  creation_time: Date;
  is_confirmed: boolean;
  rule_fingerprint: string;
  same_incident_in_the_past_id: string;
  following_incidents_ids: string[];
  merged_into_incident_id: string;
  merged_by: string;
  merged_at: Date;
  fingerprint: string;
  enrichments: { [key: string]: any };
}

export interface IncidentCandidateDto {
  id: string;
  name: string;
  description: string;
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
