import { Scope } from "@/app/(keep)/settings/models";
import { useSession } from "next-auth/react";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { useApiUrl } from "./useConfig";
import { fetcher } from "utils/fetcher";

export const useScopes = (options: SWRConfiguration = {}) => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  return useSWRImmutable<string[]>(
    () => (session ? `${apiUrl}/auth/permissions/scopes` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
