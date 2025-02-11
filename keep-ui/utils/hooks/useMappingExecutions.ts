import { useApi } from "@/shared/lib/hooks/useApi";
import useSWR, { SWRConfiguration } from "swr";
import {
  MappingExecutionDetail,
  PaginatedMappingExecutionDto,
} from "@/shared/api/mapping-executions";

interface UseMappingExecutionsOptions {
  ruleId: string;
  limit?: number;
  offset?: number;
  options?: SWRConfiguration;
}

export function useMappingExecutions({
  ruleId,
  limit = 20,
  offset = 0,
  options = { revalidateOnFocus: false },
}: UseMappingExecutionsOptions) {
  const api = useApi();

  const { data, error, isLoading, mutate } =
    useSWR<PaginatedMappingExecutionDto>(
      api.isReady()
        ? `/mapping/${ruleId}/executions?limit=${limit}&offset=${offset}`
        : null,
      (url) => api.get(url),
      options
    );

  return {
    executions: data?.items || [],
    totalCount: data?.count || 0,
    isLoading,
    error,
    mutate,
  };
}

interface UseMappingExecutionDetailOptions {
  ruleId: string;
  executionId: string;
  options?: SWRConfiguration;
}

export function useMappingExecutionDetail({
  ruleId,
  executionId,
  options = { revalidateOnFocus: false },
}: UseMappingExecutionDetailOptions) {
  const api = useApi();

  const { data, error, isLoading, mutate } = useSWR<MappingExecutionDetail>(
    api.isReady() ? `/mapping/${ruleId}/executions/${executionId}` : null,
    (url) => api.get(url),
    options
  );

  return {
    execution: data,
    isLoading,
    error,
    mutate,
  };
}
