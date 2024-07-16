export interface IncidentDto {
  id: number;
  name: string;
  description: string;
  assignee: string;
  incident_fingerprint: string;
  start_time?: Date;
  end_time?: Date;
  creation_time: Date;
}
