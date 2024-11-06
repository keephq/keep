import { DeduplicationRule } from "app/deduplication/models";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { useApiUrl } from "./useConfig";
import { fetcher } from "utils/fetcher";

export const useDeduplicationRules = (options: SWRConfiguration = {}) => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  return useSWRImmutable<DeduplicationRule[]>(
    () => (session ? `${apiUrl}/deduplications` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};

export const useDeduplicationFields = (options: SWRConfiguration = {}) => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  return useSWRImmutable<Record<string, string[]>>(
    () => (session ? `${apiUrl}/deduplications/fields` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
