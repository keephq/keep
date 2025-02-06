import { useApi } from "@/shared/lib/hooks/useApi";
import { showSuccessToast } from "@/shared/ui/utils/showSuccessToast";
import { showErrorToast } from "@/shared/ui";
import { Definition } from "@/app/(keep)/workflows/builder/builder-store";
import { getWorkflowFromDefinition } from "@/app/(keep)/workflows/builder/utils";
import { stringify } from "yaml";
import { useCallback } from "react";
import { useWorkflowsV2 } from "utils/hooks/useWorkflowsV2";

type UseWorkflowActionsReturn = {
  createWorkflow: (
    definition: Definition
  ) => Promise<CreateOrUpdateWorkflowResponse | null>;
  updateWorkflow: (
    workflowId: string,
    definition: Definition | Record<string, unknown>,
    options?: { mutateWorkflowDetail?: () => Promise<any> }
  ) => Promise<CreateOrUpdateWorkflowResponse | null>;
  deleteWorkflow: (
    workflowId: string,
    options?: {
      skipConfirmation?: boolean;
      mutateWorkflowDetail?: () => Promise<any>;
    }
  ) => void;
};

type CreateOrUpdateWorkflowResponse = {
  workflow_id: string;
  status: "created" | "updated";
  revision: number;
};

export function useWorkflowActions(): UseWorkflowActionsReturn {
  const api = useApi();
  const { mutateWorkflows } = useWorkflowsV2();

  const createWorkflow = useCallback(
    async (definition: Definition) => {
      try {
        const workflow = getWorkflowFromDefinition(definition);
        const body = stringify(workflow);
        const response = await api.request<CreateOrUpdateWorkflowResponse>(
          "/workflows/json",
          {
            method: "POST",
            body,
            headers: { "Content-Type": "text/html" },
          }
        );
        showSuccessToast("Workflow created successfully");
        await mutateWorkflows();
        return response;
      } catch (error) {
        showErrorToast(error, "Failed to create workflow");
        return null;
      }
    },
    [api, mutateWorkflows]
  );

  const updateWorkflow = useCallback(
    async (
      workflowId: string,
      definition: Definition | Record<string, unknown>,
      options?: { mutateWorkflowDetail?: () => Promise<any> }
    ) => {
      try {
        const body = stringify(
          "workflow" in definition
            ? definition
            : getWorkflowFromDefinition(definition as Definition)
        );
        const response = await api.request<CreateOrUpdateWorkflowResponse>(
          `/workflows/${workflowId}`,
          {
            method: "PUT",
            body,
            headers: { "Content-Type": "text/html" },
          }
        );
        showSuccessToast("Workflow updated successfully");

        const mutations = [mutateWorkflows()];
        if (options?.mutateWorkflowDetail) {
          mutations.push(options.mutateWorkflowDetail());
        }
        await Promise.all(mutations);

        return response;
      } catch (error) {
        showErrorToast(error, "Failed to update workflow");
        return null;
      }
    },
    [api, mutateWorkflows]
  );

  const deleteWorkflow = useCallback(
    async (
      workflowId: string,
      options?: {
        skipConfirmation?: boolean;
        mutateWorkflowDetail?: () => Promise<any>;
      }
    ) => {
      if (
        !options?.skipConfirmation &&
        !confirm("Are you sure you want to delete this workflow?")
      ) {
        return false;
      }
      try {
        await api.delete(`/workflows/${workflowId}`);
        showSuccessToast("Workflow deleted successfully");

        const mutations = [mutateWorkflows()];
        if (options?.mutateWorkflowDetail) {
          mutations.push(options.mutateWorkflowDetail());
        }
        await Promise.all(mutations);
      } catch (error) {
        showErrorToast(error, "An error occurred while deleting workflow");
      }
    },
    [api, mutateWorkflows]
  );

  return {
    createWorkflow,
    updateWorkflow,
    deleteWorkflow,
  };
}
