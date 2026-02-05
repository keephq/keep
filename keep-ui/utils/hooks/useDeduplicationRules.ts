import { DeduplicationRule } from "@/app/(keep)/deduplication/models";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useDeduplicationRules = (options: SWRConfiguration = {}) => {
  const api = useApi();

  return useSWRImmutable<DeduplicationRule[]>(
    api.isReady() ? "/deduplications" : null,
    (url) => api.get(url),
    options
  );
};

export const useDeduplicationFields = (options: SWRConfiguration = {}) => {
  const api = useApi();

  return useSWRImmutable<Record<string, string[]>>(
    api.isReady() ? "/deduplications/fields" : null,
    (url) => api.get(url),
    options
  );
};
