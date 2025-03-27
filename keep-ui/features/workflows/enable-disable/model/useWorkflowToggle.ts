import { useState } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { useWorkflowRevalidation } from "@/entities/workflows/model/useWorkflowsRevalidation";

export const useToggleWorkflow = (workflowId: string) => {
  const api = useApi();
  const [isToggling, setIsToggling] = useState(false);
  const { revalidateWorkflow } = useWorkflowRevalidation();
  const toggleWorkflow = async () => {
    try {
      setIsToggling(true);
      await api.put(`/workflows/${workflowId}/toggle`);

      // Revalidate both the specific workflow and the workflows list
      revalidateWorkflow(workflowId);
    } catch (error) {
      showErrorToast(error, "Failed to toggle workflow state");
    } finally {
      setIsToggling(false);
    }
  };

  return {
    toggleWorkflow,
    isToggling,
  };
};
