import { useApi } from "@/shared/lib/hooks/useApi";
import useSWR, { SWRConfiguration } from "swr";
import {
  EnrichmentEvent,
  EnrichmentEventWithLogs,
  PaginatedMappingExecutionDto,
} from "@/shared/api/enrichment-events";

interface UseEnrichmentEventsOptions {
  ruleId: string;
  limit?: number;
  offset?: number;
  options?: SWRConfiguration;
}

export function useEnrichmentEvents({
  ruleId,
  limit = 20,
  offset = 0,
  options = { revalidateOnFocus: false },
}: UseEnrichmentEventsOptions) {
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

interface UseEnrichmentEventOptions {
  ruleId: string;
  executionId: string;
  options?: SWRConfiguration;
}

export function useEnrichmentEvent({
  ruleId,
  executionId,
  options = { revalidateOnFocus: false },
}: UseEnrichmentEventOptions) {
  const api = useApi();

  const { data, error, isLoading, mutate } = useSWR<EnrichmentEventWithLogs>(
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
