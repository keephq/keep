import useSWR, { SWRConfiguration } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { workflowKeys } from "./workflowKeys";
import { WorkflowRevisionList } from "@/shared/api/workflows";

export function useWorkflowRevisions(
  workflowId: string | null,
  options?: SWRConfiguration<WorkflowRevisionList>
) {
  const api = useApi();

  const cacheKey =
    api.isReady() && workflowId ? workflowKeys.revisions(workflowId) : null;

  return useSWR<WorkflowRevisionList>(
    cacheKey,
    () => api.get(`/workflows/${workflowId}/versions`),
    options
  );
}
