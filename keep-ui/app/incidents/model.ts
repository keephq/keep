import {AlertDto} from "../alerts/models";

export interface IncidentDto {
  id: string;
  name: string;
  description: string;
  assignee: string;
  severity: string;
  number_of_alerts: number;
  alert_sources: string[];
  services: string[];
  start_time?: Date;
  end_time?: Date;
  creation_time: Date;
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

