import { useApi } from "@/shared/lib/hooks/useApi";
import useSWR, { SWRConfiguration } from "swr";
import { KeepApiError } from "@/shared/api";
import { showErrorToast } from "@/shared/ui/utils/showErrorToast";

export interface ProviderLog {
  id: string;
  tenant_id: string;
  provider_id: string;
  timestamp: string;
  log_message: string;
  log_level: string;
  context: Record<string, any>;
  execution_id: string;
}

interface UseProviderLogsOptions {
  providerId: string;
  limit?: number;
  startTime?: string;
  endTime?: string;
  options?: SWRConfiguration;
}

export function useProviderLogs({
  providerId,
  limit = 100,
  startTime,
  endTime,
  options = { revalidateOnFocus: false },
}: UseProviderLogsOptions) {
  const api = useApi();

  const queryParams = new URLSearchParams();
  if (limit) queryParams.append("limit", limit.toString());
  if (startTime) queryParams.append("start_time", startTime);
  if (endTime) queryParams.append("end_time", endTime);

  const { data, error, isLoading, mutate } = useSWR<ProviderLog[], Error>(
    // Only make the request if providerId exists and api is ready
    providerId && api.isReady()
      ? `/providers/${providerId}/logs?${queryParams.toString()}`
      : null,
    (url) => api.get(url),
    {
      ...options,
      shouldRetryOnError: false, // Prevent infinite retry on authentication errors
    }
  );

  return {
    logs: data || [],
    isLoading,
    error,
    refresh: mutate,
  };
}
