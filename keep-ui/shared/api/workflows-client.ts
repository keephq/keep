import { Definition } from "@/app/(keep)/workflows/builder/types";
import { getWorkflowFromDefinition } from "@/app/(keep)/workflows/builder/utils";
import { stringify } from "yaml";
import { getClientApiInstance } from "./client";

export const workflowsApi = {
  async getWorkflow(workflowId: string) {
    const api = getClientApiInstance();
    return api.get(`/workflows/${workflowId}`);
  },

  async createWorkflow(definition: Definition) {
    const api = getClientApiInstance();
    const workflow = getWorkflowFromDefinition(definition);
    const body = stringify(workflow);
    return api.request("/workflows/json", {
      method: "POST",
      body,
      headers: { "Content-Type": "text/html" },
    });
  },

  async updateWorkflow(workflowId: string, definition: Definition) {
    const api = getClientApiInstance();
    const body = stringify(getWorkflowFromDefinition(definition));
    return api.request(`/workflows/${workflowId}`, {
      method: "PUT",
      body,
      headers: { "Content-Type": "text/html" },
    });
  },
};
