import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useTenantConfigurationKey = <T>(
  key: string,
  options: SWRConfiguration = {}
) => {
  const api = useApi();

  return useSWRImmutable<T>(
    api.isReady() ? `/settings/tenant/configuration/${key}` : null,
    (url) => api.get(url),
    options
  );
};
