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
  fatigueMeter?: number;
  url?: string;
  pushed: boolean;
  generatorURL?: string;
  fingerprint: string;
  deleted: string[];
  assignees?: { [lastReceived: string]: string };
  ticket_url: string;
  playbook_url?: string;
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
  "message",
  "description",
  "severity",
  "fatigueMeter",
  "pushed",
  "url",
  "event_id",
  "ticket_url",
  "playbook_url",
  "ack_status",
  "deleted",
  "assignee",
];
