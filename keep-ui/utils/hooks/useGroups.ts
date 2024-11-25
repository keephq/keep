import { Group } from "@/app/(keep)/settings/models";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useGroups = (options: SWRConfiguration = {}) => {
  const api = useApi();

  return useSWRImmutable<Group[]>(
    api.isReady() ? "/auth/groups" : null,
    api.get,
    options
  );
};
