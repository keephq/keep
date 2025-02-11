export interface MappingLogEntry {
  timestamp: string;
  message: string;
  context?: Record<string, any>;
}

export interface MappingExecutionDetail {
  id: string;
  rule_id: number;
  rule_name?: string;
  alert_id: string;
  status: string;
  started: string;
  execution_time?: number;
  error?: string | null;
  logs?: MappingLogEntry[] | null;
  enriched_fields?: Record<string, any>;
  tenant_id: string;
  created_by?: string;
  created_at: string;
  updated_by?: string | null;
  last_updated_at?: string | null;
  type: "csv" | "topology";
  matchers: string[][];
  rows?: Record<string, any>[];
  disabled?: boolean;
  override?: boolean;
  condition?: string;
}

export interface PaginatedMappingExecutionDto {
  limit: number;
  offset: number;
  count: number;
  items: MappingExecutionDetail[];
}

export type MappingExecutionFailure = Pick<MappingExecutionDetail, "error">;

export function isMappingExecution(data: any): data is MappingExecutionDetail {
  return "id" in data && "rule_id" in data;
}
