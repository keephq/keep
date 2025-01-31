import { Permission } from "@/app/(keep)/settings/models";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { useApi } from "@/shared/lib/hooks/useApi";

export const usePermissions = (options: SWRConfiguration = {}) => {
  const api = useApi();

  return useSWRImmutable<Permission[]>(
    api.isReady() ? "/auth/permissions" : null,
    (url) => api.get(url),
    options
  );
};
