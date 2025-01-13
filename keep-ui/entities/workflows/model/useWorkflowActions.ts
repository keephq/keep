import { useApi } from "@/shared/lib/hooks/useApi";
import { showSuccessToast } from "@/shared/ui/utils/showSuccessToast";
import { useRevalidateMultiple } from "@/shared/lib/state-utils";
import { showErrorToast } from "@/shared/ui";
import { Definition } from "@/app/(keep)/workflows/builder/builder-store";
import { getWorkflowFromDefinition } from "@/app/(keep)/workflows/builder/utils";
import { stringify } from "yaml";
import { useCallback } from "react";

type UseWorkflowActionsReturn = {
  createWorkflow: (
    definition: Definition
  ) => Promise<CreateOrUpdateWorkflowResponse | null>;
  deleteWorkflow: (workflowId: string) => void;
};

type CreateOrUpdateWorkflowResponse = {
  workflow_id: string;
  status: "created" | "updated";
  revision: number;
};

/**
 * Provides actions for creating and deleting workflows.
 * 
 * @returns An object containing methods to create and delete workflows
 * 
 * @remarks
 * This hook encapsulates API interactions for workflow management, including:
 * - Creating a new workflow from a definition
 * - Deleting an existing workflow
 * - Automatically refreshing the workflows list after successful operations
 * 
 * @example
 * const { createWorkflow, deleteWorkflow } = useWorkflowActions();
 * await createWorkflow(myWorkflowDefinition);
 * await deleteWorkflow('workflow-123');
 */
export function useWorkflowActions(): UseWorkflowActionsReturn {
  const api = useApi();
  const revalidateMultiple = useRevalidateMultiple();
  const refreshWorkflows = useCallback(() => {
    revalidateMultiple(["/workflows?is_v2=true"], { isExact: true });
  }, [revalidateMultiple]);

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
        refreshWorkflows();
        return response;
      } catch (error) {
        showErrorToast(error, "An error occurred while creating workflow");
        return null;
      }
    },
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
    deleteWorkflow,
  };
}
