import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Tag } from "@/app/(keep)/alerts/models";

export const useTags = (options: SWRConfiguration = {}) => {
  const api = useApi();

  return useSWRImmutable<Tag[]>(
    api.isReady() ? "/tags" : null,
    (url) => api.get(url),
    options
  );
};
