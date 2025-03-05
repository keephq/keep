import { useApi } from "@/shared/lib/hooks/useApi";
import { useMemo, useState } from "react";
import useSWR from "swr";

type UseHealthResult = {
  isHealthy: boolean;
  lastChecked: number;
  checkHealth: () => Promise<void>;
};

const CACHE_DURATION = 30000;

export function useHealth(): UseHealthResult {
  const api = useApi();
  const [lastChecked, setLastChecked] = useState(0);

  const {
    data: health,
    error,
    mutate: mutateHealth,
  } = useSWR(
    "/healthcheck",
    () =>
      api.request("/healthcheck", {
        method: "GET",
        // Short timeout to avoid blocking
        signal: AbortSignal.timeout(2000),
      }),
    {
      refreshInterval: CACHE_DURATION,
      onError: (error) => {
        setLastChecked(Date.now());
      },
      onSuccess: () => {
        setLastChecked(Date.now());
      },
    }
  );

  const isHealthy = !error;

  return useMemo(
    () => ({ isHealthy, lastChecked, checkHealth: mutateHealth }),
    [isHealthy, lastChecked, mutateHealth]
  );
}
