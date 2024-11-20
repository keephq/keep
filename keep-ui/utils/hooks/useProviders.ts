import { useSession } from "next-auth/react";
import { useApiUrl } from "./useConfig";
import { SWRConfiguration } from "swr";
import { ProvidersResponse } from "@/app/(keep)/providers/providers";
import { fetcher } from "../fetcher";
import useSWRImmutable from "swr/immutable";

export const useProviders = (
  options: SWRConfiguration = { revalidateOnFocus: false }
) => {
  const { data: session } = useSession();
  const apiUrl = useApiUrl();

  return useSWRImmutable<ProvidersResponse>(
    () => (session ? `${apiUrl}/providers` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
