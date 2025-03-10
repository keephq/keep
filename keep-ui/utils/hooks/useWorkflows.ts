import { Workflow } from "@/shared/api/workflows";
import { useApi } from "@/shared/lib/hooks/useApi";
import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";

export const useWorkflows = (options?: SWRConfiguration) => {
  const api = useApi();

  const swr = useSWRImmutable(
    api.isReady() ? "/workflows" : null,
    (url) => api.get(url),
    options
  );

  return {
    ...swr,
    data: swr.data?.results as Workflow[],
  };
};
