import { WorkflowTemplate } from "@/shared/api/workflows";
import { useApi } from "@/shared/lib/hooks/useApi";
import useSWR, { SWRConfiguration } from "swr";

export interface WorkflowTemplatesQuery {
  cel: string;
  limit: number;
  offset: number;
}

export function useQueryWorkflowTemplate(
  query: WorkflowTemplatesQuery,
  options?: SWRConfiguration<any>
) {
  const api = useApi();
  const requestUrl = `/workflows/templates/query`;
  const { data, error, isLoading, mutate } = useSWR<any>(
    api.isReady() && query
      ? `/workflows/templates/query` + JSON.stringify(query)
      : null,
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
