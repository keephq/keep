import { notFound } from "next/navigation";
import { ApiClient } from "./ApiClient";
import { KeepApiError } from "./KeepApiError";
import { createServerApiClient } from "./server";
import { cache } from "react";

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
  alertRule?: boolean;
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

// TODO: replace with updated client api and server api client approach
export async function getWorkflow(api: ApiClient, id: string) {
  return await api.get<Workflow>(`/workflows/${id}`);
}

/**
 * Fetches a workflow by ID with error handling for 404 cases
 * @param id - The unique identifier of the workflow to retrieve
 * @returns Promise containing the workflow data or undefined if not found
 * @returns {never} If 404 error occurs (handled by Next.js notFound) or if the API request fails for reasons other than 404
 */
export async function _getWorkflowWithRedirectSafe(
  id: string
): Promise<Workflow | undefined> {
  try {
    const api = await createServerApiClient();
    return await getWorkflow(api, id);
  } catch (error) {
    if (error instanceof KeepApiError && error.statusCode === 404) {
      notFound();
    } else {
      console.error(error);
      return undefined;
    }
  }
}

// cache the function for server side, so we can use it in the layout, metadata and in the page itself
export const getWorkflowWithRedirectSafe = cache(_getWorkflowWithRedirectSafe);
