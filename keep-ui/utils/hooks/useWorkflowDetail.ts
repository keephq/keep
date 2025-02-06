import useSWR, { mutate } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Workflow } from "@/shared/api/workflows";

export function useWorkflowDetail(workflowId: string, initialData?: Workflow) {
  const api = useApi();

  const workflowKey = `/workflows/${workflowId}`;

  const {
    data: workflow,
    error,
    isLoading,
  } = useSWR<Workflow>(
    api.isReady() ? workflowKey : null,
    (url: string) => api.get(url),
    {
      fallbackData: initialData,
    }
  );

  const mutateWorkflowDetail = async () => {
    await mutate(workflowKey);
    // Also mutate the workflows list if it exists in the cache
    await mutate("/workflows?is_v2=true");
  };

  return {
    workflow,
    isLoading,
    error,
    mutateWorkflowDetail,
  };
}
