import { WorkflowExecutionDetail } from "@/shared/api/workflow-executions";
import useSWR from "swr";
import { workflowExecutionsKeys } from "./workflowExecutionsKeys";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useWorkflowExecutionDetail = (
  workflowId: string,
  workflowExecutionId: string
) => {
  const api = useApi();

  const cacheKey =
    api.isReady() && workflowId && workflowExecutionId
      ? workflowExecutionsKeys.detail(workflowId, workflowExecutionId)
      : null;

  return useSWR<WorkflowExecutionDetail>(cacheKey, () =>
    api.get(`/workflows/${workflowId}/runs/${workflowExecutionId}`)
  );
};
