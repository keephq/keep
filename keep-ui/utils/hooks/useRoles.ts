import { Role } from "@/app/(keep)/settings/models";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useRoles = (options: SWRConfiguration = {}) => {
  const api = useApi();

  return useSWRImmutable<Role[]>(
    api.isReady() ? "/auth/roles" : null,
    (url) => api.get(url),
    options
  );
};
