export interface IncidentDto {
  id: number;
  name: string;
  description: string;
  assignee: string;
  severity: string;
  number_of_alerts: number;
  alert_sources: string[];
  services: string[];
  incident_fingerprint: string;
  start_time?: Date;
  end_time?: Date;
  creation_time: Date;
}
