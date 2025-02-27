import { useApi } from "@/shared/lib/hooks/useApi";
import { showSuccessToast } from "@/shared/ui/utils/showSuccessToast";
import { useRevalidateMultiple } from "@/shared/lib/state-utils";
import { showErrorToast } from "@/shared/ui";
import { Definition } from "@/entities/workflows/model/types";
import { stringify } from "yaml";
import { useCallback } from "react";
import { getYamlWorkflowDefinition } from "@/entities/workflows/lib/parser";

function getBodyFromStringOrDefinitionOrObject(
  definition: Definition | string | Record<string, unknown>
) {
  if (typeof definition === "string") {
    return definition;
  }
  if (typeof definition === "object" && "workflow" in definition) {
    return stringify(definition);
  }
  return stringify(getYamlWorkflowDefinition(definition as Definition));
}

type UseWorkflowActionsReturn = {
  createWorkflow: (
    definition: Definition | string
  ) => Promise<CreateOrUpdateWorkflowResponse | null>;
  updateWorkflow: (
    workflowId: string,
    definition: Definition | Record<string, unknown> | string
  ) => Promise<CreateOrUpdateWorkflowResponse | null>;
  deleteWorkflow: (workflowId: string) => void;
};

type CreateOrUpdateWorkflowResponse = {
  workflow_id: string;
  status: "created" | "updated";
  revision: number;
};

export function useWorkflowActions(): UseWorkflowActionsReturn {
  const api = useApi();
  const revalidateMultiple = useRevalidateMultiple();
  const refreshWorkflows = useCallback(() => {
    revalidateMultiple(["/workflows?is_v2=true"], { isExact: true });
  }, [revalidateMultiple]);

  const createWorkflow = useCallback(
    async (definition: Definition | string) => {
      try {
        const body = getBodyFromStringOrDefinitionOrObject(definition);
        const response = await api.request<CreateOrUpdateWorkflowResponse>(
          "/workflows/json",
          {
            method: "POST",
            body,
            headers: { "Content-Type": "application/yaml" },
          }
        );
        showSuccessToast("Workflow created successfully");
        refreshWorkflows();
        return response;
      } catch (error) {
        showErrorToast(error, "Failed to create workflow");
        return null;
      }
    },
    [api, refreshWorkflows]
  );

  const updateWorkflow = useCallback(
    async (
      workflowId: string,
      definition: Definition | Record<string, unknown> | string
    ) => {
      try {
        const body = getBodyFromStringOrDefinitionOrObject(definition);
        const response = await api.request<CreateOrUpdateWorkflowResponse>(
          `/workflows/${workflowId}`,
          {
            method: "PUT",
            body,
            headers: { "Content-Type": "application/yaml" },
          }
        );
        showSuccessToast("Workflow updated successfully");
        revalidateMultiple([`/workflows/${workflowId}`], { isExact: true });
        refreshWorkflows();
        return response;
      } catch (error) {
        showErrorToast(error, "Failed to update workflow");
        return null;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [api, refreshWorkflows]
  );

  const deleteWorkflow = useCallback(
    async (
      workflowId: string,
      { skipConfirmation = false }: { skipConfirmation?: boolean } = {}
    ) => {
      if (
        !skipConfirmation &&
        !confirm("Are you sure you want to delete this workflow?")
      ) {
        return false;
      }
      try {
        await api.delete(`/workflows/${workflowId}`);
        showSuccessToast("Workflow deleted successfully");
        refreshWorkflows();
      } catch (error) {
        showErrorToast(error, "An error occurred while deleting workflow");
      }
    },
    [api, refreshWorkflows]
  );

  return {
    createWorkflow,
    updateWorkflow,
    deleteWorkflow,
  };
}
