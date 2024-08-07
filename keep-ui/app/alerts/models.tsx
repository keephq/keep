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
}

export const reverseSeverityMapping: { [id: string]: number } = {
  [Severity.Low]: 1,
  [Severity.Info]: 2,
  [Severity.Warning]: 3,
  [Severity.High]: 4,
  [Severity.Critical]: 5,
}

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
  isNoisy?: boolean;
  enriched_fields: string[];
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
  is_noisy: boolean;
  should_do_noise_now: boolean;
  alerts_count: number;
  created_by?: string;
}

export function getTabsFromPreset(preset: Preset): any[] {
  const tabsOption = preset.options.find(option => option.label.toLowerCase() === "tabs");
  return tabsOption && Array.isArray(tabsOption.value) ? tabsOption.value : [];
}

export interface AlertToWorkflowExecution {
  workflow_id: string;
  workflow_execution_id: string;
  alert_fingerprint: string;
  workflow_status: "timeout" | "in_progress" | "success" | "error" | "providers_not_configured";
  workflow_started: Date;
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
