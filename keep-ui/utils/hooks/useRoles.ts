import { Role } from "app/settings/models";
import { useSession } from "next-auth/react";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const useRoles = (options: SWRConfiguration = {}) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWRImmutable<Role[]>(
    () => (session ? `${apiUrl}/auth/roles` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
