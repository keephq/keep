import {AlertDto} from "../alerts/models";

export interface IncidentDto {
  id: string;
  user_generated_name: string;
  ai_generated_name: string;
  user_summary: string;
  generated_summary: string;
  assignee: string;
  severity: string;
  number_of_alerts: number;
  alert_sources: string[];
  services: string[];
  start_time?: Date;
  last_seen_time?: Date;
  end_time?: Date;
  creation_time: Date;
  is_confirmed: boolean;
  rule_fingerprint: string;
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

