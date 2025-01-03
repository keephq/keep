import { useApi } from "@/shared/lib/hooks/useApi";
import { useCallback, useEffect, useMemo, useState } from "react";

type UseHealthResult = {
  isHealthy: boolean;
  lastChecked: number;
  checkHealth: () => Promise<void>;
};

const CACHE_DURATION = 30000;

export function useHealth(): UseHealthResult {
  const api = useApi();
  const [isHealthy, setIsHealthy] = useState(true);
  const [lastChecked, setLastChecked] = useState(0);

  const checkHealth = useCallback(async () => {
    // Skip if checked recently
    if (Date.now() - lastChecked < CACHE_DURATION) {
      return;
    }

    try {
      await api.request("/healthcheck", {
        method: "GET",
        // Short timeout to avoid blocking
        signal: AbortSignal.timeout(2000),
      });
      setIsHealthy(true);
    } catch (error) {
      setIsHealthy(false);
    }
    setLastChecked(Date.now());
  }, [api]);

  useEffect(() => {
    if (!lastChecked) {
      checkHealth();
    }
  }, [checkHealth, lastChecked]);

  return useMemo(
    () => ({ isHealthy, lastChecked, checkHealth }),
    [isHealthy, lastChecked, checkHealth]
  );
}
