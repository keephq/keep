import { Step } from "sequential-workflow-designer";
export interface KeepStep extends Step {}

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
  logs?: LogEntry[] | null;
  error?: string | null;
  execution_time?: number;
}

export type WorkflowExecutionFailure = Pick<WorkflowExecution, "error">;

export function isWorkflowExecution(data: any): data is WorkflowExecution {
  return "id" in data;
}
