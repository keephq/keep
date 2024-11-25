import { Workflow } from "@/app/(keep)/workflows/models";
import { useApi } from "@/shared/lib/hooks/useApi";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";

export const useWorkflows = (options: SWRConfiguration = {}) => {
  const api = useApi();

  return useSWRImmutable<Workflow[]>(
    api.isReady() ? "/workflows" : null,
    (url) => api.get(url),
    options
  );
};
