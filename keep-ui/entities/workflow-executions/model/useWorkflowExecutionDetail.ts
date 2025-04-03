import {
  WorkflowExecutionDetail,
  WorkflowExecutionFailure,
} from "@/shared/api/workflow-executions";
import useSWR, { SWRConfiguration } from "swr";
import { workflowExecutionsKeys } from "./workflowExecutionsKeys";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useWorkflowExecutionDetail = (
  workflowId: string | null,
  workflowExecutionId: string | null,
  options?: SWRConfiguration<WorkflowExecutionDetail | WorkflowExecutionFailure>
) => {
  const api = useApi();

  const cacheKey =
    api.isReady() && workflowExecutionId
      ? workflowExecutionsKeys.detail(workflowId, workflowExecutionId)
      : null;

  const requestUrl = workflowId
    ? `/workflows/${workflowId}/runs/${workflowExecutionId}`
    : `/workflows/runs/${workflowExecutionId}`;

  return useSWR<WorkflowExecutionDetail | WorkflowExecutionFailure>(
    cacheKey,
    () => api.get(requestUrl),
    options
  );
};
