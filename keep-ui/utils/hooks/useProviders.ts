import { useSession } from "next-auth/react";
import { getApiURL } from "../apiUrl";
import useSWR, { SWRConfiguration } from "swr";
import { ProvidersResponse } from "app/providers/providers";
import { fetcher } from "../fetcher";

export const useProviders = (options?: SWRConfiguration) => {
  const { data: session } = useSession();
  const apiUrl = getApiURL();

  return useSWR<ProvidersResponse>(
    () => (session ? `${apiUrl}/providers` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
