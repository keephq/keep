import { useSession } from "next-auth/react";
import { getApiURL } from "../apiUrl";
import { SWRConfiguration } from "swr";
import { ProvidersResponse } from "app/providers/providers";
import { fetcher } from "../fetcher";
import useSWRImmutable from "swr/immutable";

export const useProviders = (options: SWRConfiguration = {}) => {
  const { data: session } = useSession();
  const apiUrl = getApiURL();

  return useSWRImmutable<ProvidersResponse>(
    () => (session ? `${apiUrl}/providers` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
