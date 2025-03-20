import { Workflow } from "@/shared/api/workflows";

export interface LogEntry {
  timestamp: string;
  message: string;
  context?: Record<string, any>;
}

export interface WorkflowExecutionDetail {
  error?: string | null;
  event_id?: string;
  event_type?: string;
  execution_time?: number;
  id: string;
  logs?: LogEntry[] | null;
  results: Record<string, any>;
  started: string;
  status: string;
  triggered_by: string;
  workflow_id: string;
  workflow_name?: string;
  tenant_id: string;
}

export interface PaginatedWorkflowExecutionDto {
  limit: number;
  offset: number;
  count: number;
  items: WorkflowExecutionDetail[];
  workflow: Workflow;
  avgDuration: number;
  passCount: number;
  failCount: number;
}

export type WorkflowExecutionFailure = Pick<WorkflowExecutionDetail, "error">;

export function isWorkflowExecution(
  data: any
): data is WorkflowExecutionDetail {
  return typeof data === "object" && "id" in data;
}
