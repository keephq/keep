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

export async function getWorkflow(api: ApiClient, id: string) {
  return await api.get<Workflow>(`/workflows/${id}`);
}

export async function getWorkflowWithErrorHandling(
  id: string
  // @ts-ignore ignoring since not found will be handled by nextjs
): Promise<Workflow> {
  try {
    const api = await createServerApiClient();
    return await getWorkflow(api, id);
  } catch (error) {
    if (error instanceof KeepApiError && error.statusCode === 404) {
      notFound();
    } else {
      throw error;
    }
  }
}

async function _getWorkflowWithRedirectSafe(id: string) {
  try {
    return await getWorkflowWithErrorHandling(id);
  } catch (error) {
    console.error(error);
    return undefined;
  }
}

// cache the function for server side, so we can use it in the layout, metadata and in the page itself
export const getWorkflowWithRedirectSafe = cache(_getWorkflowWithRedirectSafe);
