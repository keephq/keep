import { Workflow } from "@/shared/api/workflows";

const rawWorkflow = `
workflow:
  name: Test Workflow
  description: Test Description
  triggers:
    - type: manual
  steps:
    - name: console-step
      provider:
        type: console
        with:
          message: "Hello, world!"
`;

export const mockWorkflow: Workflow = {
  id: "1",
  name: "Test Workflow",
  description: "Test Description",
  disabled: false,
  provisioned: false,
  created_by: "test",
  creation_time: "2023-01-01",
  interval: "1d",
  providers: [],
  triggers: [],
  last_execution_time: "2023-01-01",
  last_execution_status: "success",
  last_updated: "2023-01-01",
  workflow_raw: rawWorkflow,
  workflow_raw_id: "1",
};
