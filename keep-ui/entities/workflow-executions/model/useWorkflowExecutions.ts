import { AlertToWorkflowExecution } from "@/entities/alerts/model";
import useSWR, { SWRConfiguration } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";

// should be removed in favor of useWorkflowExecutionsV2?
export const useWorkflowExecutions = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();

  return useSWR<AlertToWorkflowExecution[]>(
    api.isReady() ? "/workflows/executions" : null,
    (url) => api.get(url),
    options
  );
};
