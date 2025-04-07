import useSWR, { SWRConfiguration } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Workflow } from "@/shared/api/workflows";
import { workflowKeys } from "./workflowKeys";

export function useWorkflowDetail(
  workflowId: string | null,
  options?: SWRConfiguration<Workflow>
) {
  const api = useApi();

  const cacheKey =
    api.isReady() && workflowId ? workflowKeys.detail(workflowId) : null;

  const {
    data: workflow,
    error,
    isLoading,
  } = useSWR<Workflow>(
    cacheKey,
    () => api.get(`/workflows/${workflowId}`),
    options
  );

  return {
    workflow,
    isLoading,
    error,
  };
}
