import { notFound } from "next/navigation";
import { ApiClient } from "./ApiClient";
import { KeepApiError } from "./KeepApiError";
import { createServerApiClient } from "./server";

export type Provider = {
  id: string;
  type: string; // This corresponds to the name of the icon, e.g., "slack", "github", etc.
  name: string;
  installed: boolean;
};

export type Filter = {
  key: string;
  value: string;
};

export type Trigger = {
  type: string;
  filters?: Filter[];
  value?: string;
};

export type LastWorkflowExecution = {
  execution_time: number;
  status: string;
  started: string;
};

export type Workflow = {
  id: string;
  name: string;
  description: string;
  created_by: string;
  creation_time: string;
  interval: string;
  providers: Provider[];
  triggers: Trigger[];
  disabled: boolean;
  last_execution_time: string;
  last_execution_status: string;
  last_updated: string;
  workflow_raw: string;
  workflow_raw_id: string;
  last_execution_started?: string;
  last_executions?: LastWorkflowExecution[];
  provisioned?: boolean;
};

export type MockProvider = {
  type: string;
  config: string;
  with?: {
    command?: string;
    timeout?: number;
    _from?: string;
    to?: string;
    subject?: string;
    html?: string;
  };
};

export type MockCondition = {
  assert: string;
  name: string;
  type: string;
};

export type MockAction = {
  condition: MockCondition[];
  name: string;
  provider: MockProvider;
};

export type MockStep = {
  name: string;
  provider: MockProvider;
};

export type MockTrigger = {
  type: string;
};

export type MockWorkflow = {
  id: string;
  description: string;
  triggers: MockTrigger[];
  owners: any[]; // Adjust the type if you have more specific information about the owners
  services: any[]; // Adjust the type if you have more specific information about the services
  steps: MockStep[];
  actions: MockAction[];
};

export type WorkflowTemplate = {
  name: string;
  workflow: MockWorkflow;
  workflow_raw: string;
  workflow_raw_id: string;
};

/**
 * Retrieves a workflow by its unique identifier.
 *
 * @param api - The API client used to make the request
 * @param id - The unique identifier of the workflow to retrieve
 * @returns A promise resolving to the Workflow object
 *
 * @remarks
 * This function makes a GET request to fetch a specific workflow from the server.
 */
export async function getWorkflow(api: ApiClient, id: string) {
  return await api.get<Workflow>(`/workflows/${id}`);
}

/**
 * Retrieves a workflow by ID with optional error handling and redirection.
 *
 * @remarks
 * This function attempts to fetch a workflow using the server-side API client. If the workflow is not found and redirection is enabled, it triggers a 404 not found response.
 *
 * @param id - The unique identifier of the workflow to retrieve
 * @param options - Optional configuration for error handling
 * @param options.redirect - Whether to redirect to a not found page on 404 errors (default: true)
 * @returns A Promise resolving to the Workflow object
 * @throws {KeepApiError} If an API error occurs and redirection is disabled
 *
 * @example
 * ```typescript
 * // Retrieve workflow with default redirection
 * const workflow = await getWorkflowWithErrorHandling('workflow-123');
 *
 * // Retrieve workflow without automatic redirection
 * const workflow = await getWorkflowWithErrorHandling('workflow-123', { redirect: false });
 * ```
 */
export async function getWorkflowWithErrorHandling(
  id: string,
  { redirect = true }: { redirect?: boolean } = {}
  // @ts-ignore ignoring since not found will be handled by nextjs
): Promise<Workflow> {
  try {
    const api = await createServerApiClient();
    return await getWorkflow(api, id);
  } catch (error) {
    if (error instanceof KeepApiError && error.statusCode === 404 && redirect) {
      notFound();
    } else {
      throw error;
    }
  }
}

/**
 * Safely retrieves a workflow by ID with error suppression.
 * 
 * @remarks
 * This method attempts to fetch a workflow without triggering redirects and silently handles any errors.
 * 
 * @param id - The unique identifier of the workflow to retrieve
 * @returns The workflow if successfully retrieved, otherwise undefined
 * 
 * @throws {Error} Logs any encountered errors to the console
 */
export async function getWorkflowWithRedirectSafe(id: string) {
  try {
    return await getWorkflowWithErrorHandling(id, { redirect: false });
  } catch (error) {
    console.error(error);
    return undefined;
  }
}
