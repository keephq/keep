import { Workflow } from "../models";

export interface LogEntry {
  timestamp: string;
  message: string;
  context: string;
}

export interface WorkflowExecution {
  id: string;
  workflow_id: string;
  tenant_id: string;
  started: string;
  triggered_by: string;
  status: string;
  results: Record<string, any>;
  workflow_name?: string;
  logs?: LogEntry[] | null;
  error?: string | null;
  execution_time?: number;
}

export interface PaginatedWorkflowExecutionDto {
  limit: number;
  offset: number;
  count: number;
  items: WorkflowExecution[];
  workflow: Workflow;
  avgDuration: number;
  passCount: number;
  failCount: number;
}

export type WorkflowExecutionFailure = Pick<WorkflowExecution, "error">;

export function isWorkflowExecution(data: any): data is WorkflowExecution {
  return "id" in data;
}
