import { Option } from "./alert-presets";

export enum Severity {
  Critical = "critical",
  High = "high",
  Medium = "medium",
  Low = "low",
  Info = "info",
  Error = "error",
}

export interface AlertDto {
  id: string;
  name: string;
  status: string;
  lastReceived: Date;
  environment: string;
  isDuplicate?: boolean;
  duplicateReason?: string;
  service?: string;
  source?: string[];
  message?: string;
  description?: string;
  severity?: Severity;
  url?: string;
  pushed: boolean;
  generatorURL?: string;
  fingerprint: string;
  deleted: string[];
  assignees?: { [lastReceived: string]: string };
  ticket_url: string;
  ticket_status?: string;
  playbook_url?: string;
  providerId?: string;
}

export interface Preset {
  id?: string;
  name: string;
  options: Option[];
}

export const AlertKnownKeys = [
  "id",
  "name",
  "status",
  "lastReceived",
  "environment",
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
  "assignees",
  "providerId",
];
