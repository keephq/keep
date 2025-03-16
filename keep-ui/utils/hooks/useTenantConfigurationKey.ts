import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useTenantConfiguration = (options: SWRConfiguration = {}) => {
  const api = useApi();

  return useSWRImmutable<{ [key: string]: string }>(
    api.isReady() ? `/settings/tenant/configuration/` : null,
    (url) => api.get(url),
    options
  );
};
