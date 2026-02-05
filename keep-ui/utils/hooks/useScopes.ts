import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useScopes = (options: SWRConfiguration = {}) => {
  const api = useApi();

  return useSWRImmutable<string[]>(
    api.isReady() ? "/auth/permissions/scopes" : null,
    (url) => api.get(url),
    options
  );
};
