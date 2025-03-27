import useSWR from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Workflow } from "@/shared/api/workflows";
import { workflowKeys } from "../lib/workflowKeys";

export function useWorkflowDetail(workflowId: string, initialData?: Workflow) {
  const api = useApi();

  const cacheKey =
    api.isReady() && workflowId ? workflowKeys.detail(workflowId) : null;

  const {
    data: workflow,
    error,
    isLoading,
  } = useSWR<Workflow>(cacheKey, () => api.get(`/workflows/${workflowId}`), {
    fallbackData: initialData,
  });

  return {
    workflow,
    isLoading,
    error,
  };
}
