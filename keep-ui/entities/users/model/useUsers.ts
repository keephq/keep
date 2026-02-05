import { User } from "@/app/(keep)/settings/models";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useUsers = (options: SWRConfiguration = {}) => {
  const api = useApi();

  return useSWRImmutable<User[]>(
    api.isReady() ? "/auth/users" : null,
    (url) => api.get(url),
    options
  );
};
