import { DeduplicationRule } from "app/deduplication/models";
import { useSession } from "next-auth/react";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const useDeduplicationRules = (options: SWRConfiguration = {}) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWRImmutable<DeduplicationRule[]>(
    () => (session ? `${apiUrl}/deduplications` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
