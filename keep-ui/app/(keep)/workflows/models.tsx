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

export type WorkflowExecution = {
  id: string;
  status: string;
  started: string;
  execution_time: number;
  workflow: Workflow;
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
  last_executions?: Pick<
    WorkflowExecution,
    "execution_time" | "status" | "started"
  >[];
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
