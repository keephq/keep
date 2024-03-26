export enum Severity {
  Critical = "critical",
  High = "high",
  Medium = "medium",
  Low = "low",
  Info = "info",
  Error = "error",
}

export const severityMapping: { [id: number]: string } = {
  1: Severity.Info,
  2: Severity.Low,
  3: Severity.Medium,
  4: Severity.High,
  5: Severity.Critical,
};

export interface AlertDto {
  id: string;
  name: string;
  status: string;
  lastReceived: Date;
  environment: string;
  isDuplicate?: boolean;
  duplicateReason?: string;
  service?: string;
  source: string[];
  message?: string;
  description?: string;
  severity?: Severity;
  url?: string;
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
}

interface Option {
  readonly label: string;
  readonly value: string;
}

export interface Preset {
  id: string;
  name: string;
  options: Option[];
  is_private: boolean;
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
