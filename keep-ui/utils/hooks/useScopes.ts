import { Scope } from "app/settings/models";
import { useSession } from "next-auth/react";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const useScopes = (options: SWRConfiguration = {}) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWRImmutable<Scope[]>(
    () => (session ? `${apiUrl}/auth/permissions/scopes` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
