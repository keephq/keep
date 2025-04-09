import { extractWorkflowYamlDependencies } from "@/entities/workflows/lib/parser";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui/utils/showErrorToast";
import { useCallback, useRef } from "react";
import { v4 as uuidv4 } from "uuid";

export const useWorkflowTestRun = () => {
  const currentRequestId = useRef<string | null>(null);
  const api = useApi();

  const testRunWorkflow = useCallback(
    async (
      yamlString: string,
      eventType: "alert" | "incident",
      eventPayload: any
    ) => {
      if (currentRequestId.current) {
        showErrorToast(new Error("Workflow is already running"));
        return;
      }
      const requestId = uuidv4();
      currentRequestId.current = requestId;
      const dependencies = extractWorkflowYamlDependencies(yamlString);
      if (dependencies.alert.length > 0 || dependencies.incident.length > 0) {
        // TODO: validate payload
      }
      try {
        const response = await api.post<{
          workflow_execution_id: string;
        }>(`/workflows/test`, {
          workflow_raw: yamlString,
          type: eventType,
          body: eventPayload,
        });
        if (currentRequestId.current !== requestId) {
          return;
        }
        return response;
      } catch (error) {
        throw error;
      } finally {
        if (currentRequestId.current !== requestId) {
          return;
        }
        currentRequestId.current = null;
      }
    },
    [api]
  );

  return testRunWorkflow;
};
