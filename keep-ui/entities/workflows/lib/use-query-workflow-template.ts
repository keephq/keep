import { workflowKeys } from "@/entities/workflows/model";
import { WorkflowTemplatesQuery } from "@/entities/workflows/model/useWorkflowsV2";
import { WorkflowTemplate } from "@/shared/api/workflows";
import { useApi } from "@/shared/lib/hooks/useApi";
import useSWR, { SWRConfiguration } from "swr";

export function useQueryWorkflowTemplate(
  query: WorkflowTemplatesQuery,
  options?: SWRConfiguration<any>
) {
  const api = useApi();
  const requestUrl = `/workflows/templates/query`;
  const { data, error, isLoading, mutate } = useSWR<any>(
    api.isReady() && query ? workflowKeys.templates(query) : null,
    () => api.post(requestUrl, query),
    {
      revalidateOnFocus: false,
      ...options,
    }
  );

  return {
    data: data?.results as WorkflowTemplate[],
    totalCount: data?.count,
    error,
    isLoading,
    mutate,
  };
}
