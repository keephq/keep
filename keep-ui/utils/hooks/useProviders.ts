import { SWRConfiguration } from "swr";
import { ProvidersResponse } from "@/shared/api/providers";
import useSWRImmutable from "swr/immutable";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useProviders = (
  options: SWRConfiguration = { revalidateOnFocus: false }
) => {
  const api = useApi();

  return useSWRImmutable<ProvidersResponse>(
    api.isReady() ? "/providers" : null,
    (url) => api.get(url),
    options
  );
};

export const useProvidersWithHealthCheck = (
  options: SWRConfiguration = { revalidateOnFocus: false }
) => {
  const api = useApi();

  return useSWRImmutable<ProvidersResponse>(
    api.isReady() ? "/providers/healthcheck" : null,
    (url) => api.get(url),
    options
  );
};
