import { Role } from "@/app/(keep)/settings/models";
import { useSession } from "next-auth/react";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { useApiUrl } from "./useConfig";
import { fetcher } from "utils/fetcher";

export const useRoles = (options: SWRConfiguration = {}) => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  return useSWRImmutable<Role[]>(
    () => (session ? `${apiUrl}/auth/roles` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
