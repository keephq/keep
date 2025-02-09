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
  updateWorkflow: (
    workflowId: string,
    definition: Definition | Record<string, unknown>
  ) => Promise<CreateOrUpdateWorkflowResponse | null>;
  deleteWorkflow: (workflowId: string) => void;
  testWorkflow: (
    definition: Definition
  ) => Promise<TestWorkflowResponse | null>;
};

type CreateOrUpdateWorkflowResponse = {
  workflow_id: string;
  status: "created" | "updated";
  revision: number;
};

// TODO: move to api layer
type TestWorkflowResponse = {
  workflow_execution_id: string;
  status: "success" | "error";
  error: string | null;
  results: Record<string, unknown>;
};

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
        showErrorToast(error, "Failed to create workflow");
        return null;
      }
    },
    [api, refreshWorkflows]
  );

  const updateWorkflow = useCallback(
    async (
      workflowId: string,
      definition: Definition | Record<string, unknown>
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
        revalidateMultiple([`/workflows/${workflowId}`], { isExact: true });
        refreshWorkflows();
        return response;
      } catch (error) {
        showErrorToast(error, "Failed to update workflow");
        console.error(error);
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

  const testWorkflow = useCallback(
    async (definition: Definition) => {
      const body = stringify(getWorkflowFromDefinition(definition));
      const response = await api.request<TestWorkflowResponse>(
        "/workflows/test",
        {
          method: "POST",
          body,
          headers: { "Content-Type": "text/html" },
        }
      );
      return response;
    },
    [api]
  );

  return {
    createWorkflow,
    updateWorkflow,
    deleteWorkflow,
    testWorkflow,
  };
}
