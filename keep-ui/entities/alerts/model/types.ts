export enum Severity {
  Critical = "critical",
  High = "high",
  Warning = "warning",
  Low = "low",
  Info = "info",
  Error = "error",
}

export const severityMapping: { [id: number]: string } = {
  1: Severity.Low,
  2: Severity.Info,
  3: Severity.Warning,
  4: Severity.High,
  5: Severity.Critical,
};

export const reverseSeverityMapping: { [id: string]: number } = {
  [Severity.Low]: 1,
  [Severity.Info]: 2,
  [Severity.Warning]: 3,
  [Severity.High]: 4,
  [Severity.Critical]: 5,
};

export enum Status {
  Firing = "firing",
  Resolved = "resolved",
  Acknowledged = "acknowledged",
  Suppressed = "suppressed",
  Pending = "pending",
}

export interface AlertDto {
  id: string;
  event_id: string;
  name: string;
  status: Status;
  lastReceived: Date;
  environment: string;
  isDuplicate?: boolean;
  duplicateReason?: string;
  service?: string;
  source: string[];
  message?: string;
  description?: string;
  description_format?: "markdown" | "html" | null;
  severity?: Severity;
  url?: string;
  imageUrl?: string;
  pushed: boolean;
  generatorURL?: string;
  fingerprint: string;
  deleted: boolean;
  dismissed: boolean;
  assignee?: string;
  ticket_url: string;
  ticket_status?: string;
  playbook_url?: string;
  providerId?: string;
  group?: boolean;
  note?: string;
  isNoisy?: boolean;
  enriched_fields: string[];
  incident?: string;
  alert_query?: string;

  // From AlertWithIncidentLinkMetadataDto
  is_created_by_ai?: boolean;
}

export interface AlertToWorkflowExecution {
  workflow_id: string;
  workflow_execution_id: string;
  alert_fingerprint: string;
  workflow_status:
    | "timeout"
    | "in_progress"
    | "success"
    | "error"
    | "providers_not_configured";
  workflow_started: Date;
  event_id: string;
}

export const AlertKnownKeys = [
  "id",
  "name",
  "status",
  "lastReceived",
  "isDuplicate",
  "duplicateReason",
  "source",
  "description",
  "severity",
  "pushed",
  "url",
  "event_id",
  "ticket_url",
  "playbook_url",
  "ack_status",
  "deleted",
  "assignee",
  "providerId",
  "checkbox",
  "alertMenu",
  "group",
  "extraPayload",
  "note",
];

export interface ViewedAlert {
  fingerprint: string;
  viewedAt: string;
}

export type AuditEvent = {
  id: string;
  user_id: string;
  action: string;
  description: string;
  timestamp: string;
  fingerprint: string;
};

export interface AlertsQuery {
  cel?: string;
  offset?: number;
  limit?: number;
  sortOptions?: { sortBy: string; sortDirection?: "ASC" | "DESC" }[];
}
