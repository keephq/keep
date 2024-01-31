import { useSession } from "next-auth/react";
import { getApiURL } from "../apiUrl";
import useSWR, { SWRConfiguration } from "swr";
import { ProvidersResponse } from "app/providers/providers";
import { fetcher } from "../fetcher";

export const useProviders = (options?: SWRConfiguration) => {
  const { data: session } = useSession();
  const apiUrl = getApiURL();

  // Default options
  const defaultOptions: SWRConfiguration = {
    revalidateOnFocus: false,
    revalidateOnMount: false,
  };

  return useSWR<ProvidersResponse>(
    () => (session ? `${apiUrl}/providers` : null),
    (url) => fetcher(url, session?.accessToken),
    { ...defaultOptions, ...options } // Combine default options with user-provided options
  );
};
