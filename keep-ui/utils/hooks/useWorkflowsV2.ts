import useSWR, { mutate } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Workflow } from "@/shared/api/workflows";

const WORKFLOWS_KEY = "/workflows?is_v2=true";

export function useWorkflowsV2() {
  const api = useApi();

  const { data, error, isLoading } = useSWR<any>(
    api.isReady() ? WORKFLOWS_KEY : null,
    (url: string) => api.get(url)
  );

  const mutateWorkflows = () => {
    return mutate(WORKFLOWS_KEY);
  };

  return {
    workflows: data?.results as Workflow[],
    isLoading,
    error,
    mutateWorkflows,
  };
}
