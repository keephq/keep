export enum Severity {
  Critical = "critical",
  High = "high",
  Medium = "medium",
  Low = "low",
  Info = "info",
}

export interface Alert {
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
  pushed: boolean;
}

export const AlertKnownKeys = [
  "id",
  "name",
  "status",
  "lastReceived",
  "environment",
  "isDuplicate",
  "duplicateReason",
  "service",
  "source",
  "message",
  "description",
  "severity",
  "fatigueMeter",
  "pushed",
];

export const AlertTableKeys: string[] = [
  "Severity",
  "Status",
  "Fatigue Meter",
  "Last Received",
  "Duplicate",
  "Environment",
  "Service",
  "Source",
  "Description",
  "Message",
  "Payload",
];
