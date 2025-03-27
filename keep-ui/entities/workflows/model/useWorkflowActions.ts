import { useApi } from "@/shared/lib/hooks/useApi";
import { showSuccessToast } from "@/shared/ui/utils/showSuccessToast";
import { showErrorToast } from "@/shared/ui";
import { Definition } from "@/entities/workflows/model/types";
import { useCallback } from "react";
import { KeepApiError } from "@/shared/api/KeepApiError";
import { getBodyFromStringOrDefinitionOrObject } from "../lib/yaml-utils";
import { useWorkflowRevalidation } from "./useWorkflowRevalidation";

type DeleteOptions = {
  skipConfirmation?: boolean;
};

type UseWorkflowActionsReturn = {
  uploadWorkflowFiles: (files: FileList) => Promise<string[]>;
  createWorkflow: (
    definition: Definition | string
  ) => Promise<CreateOrUpdateWorkflowResponse | null>;
  updateWorkflow: (
    workflowId: string,
    definition: Definition | Record<string, unknown> | string
  ) => Promise<CreateOrUpdateWorkflowResponse | null>;
  deleteWorkflow: (
    workflowId: string,
    options?: DeleteOptions
  ) => Promise<boolean>;
};

type CreateOrUpdateWorkflowResponse = {
  workflow_id: string;
  status: "created" | "updated";
  revision: number;
};

export function useWorkflowActions(): UseWorkflowActionsReturn {
  const api = useApi();
  const { revalidateWorkflow, revalidateLists } = useWorkflowRevalidation();

  const uploadWorkflowFiles = useCallback(
    async (files: FileList) => {
      const uploadFile = async (formData: FormData, fName: string) => {
        try {
          const response = await api.request<CreateOrUpdateWorkflowResponse>(
            `/workflows`,
            {
              method: "POST",
              body: formData,
            }
          );

          revalidateWorkflow(response.workflow_id);

          return response;
        } catch (error) {
          if (error instanceof KeepApiError) {
            showErrorToast(
              error,
              `Failed to upload ${fName}: ${error.message}`
            );
          } else {
            showErrorToast(error, "Failed to upload file");
          }
        }
      };

      const formData = new FormData();
      const uploadedWorkflowsIds: string[] = [];

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const fName = file.name;
        formData.set("file", file);
        const response = await uploadFile(formData, fName);
        if (response?.workflow_id) {
          uploadedWorkflowsIds.push(response.workflow_id);
        }
      }

      if (uploadedWorkflowsIds.length === 0) {
        return [];
      }

      const plural =
        uploadedWorkflowsIds.length === 1 ? "workflow" : "workflows";
      revalidateLists();
      showSuccessToast(
        `${uploadedWorkflowsIds.length} ${plural} uploaded successfully`
      );
      return uploadedWorkflowsIds;
    },
    [api, revalidateWorkflow, revalidateLists]
  );

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
        revalidateWorkflow(response.workflow_id);
        return response;
      } catch (error) {
        showErrorToast(error, "Failed to create workflow");
        return null;
      }
    },
    [api, revalidateWorkflow]
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
        revalidateWorkflow(workflowId);
        return response;
      } catch (error) {
        showErrorToast(error, "Failed to update workflow");
        return null;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [api, revalidateWorkflow]
  );

  const deleteWorkflow = useCallback(
    async (
      workflowId: string,
      { skipConfirmation = false }: DeleteOptions = {}
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
        revalidateWorkflow(workflowId);
        return true;
      } catch (error) {
        console.error(error);
        showErrorToast(error, "An error occurred while deleting workflow");
        return false;
      }
    },
    [api, revalidateWorkflow]
  );

  return {
    createWorkflow,
    updateWorkflow,
    deleteWorkflow,
    uploadWorkflowFiles,
  };
}
