import { MappingRule } from "@/app/(keep)/mapping/models";
import useSWR, { SWRConfiguration } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useMappings = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();

  return useSWR<MappingRule[]>(
    api.isReady() ? "/mapping" : null,
    (url) => api.get(url),
    options
  );
};

export const useMappingRule = (
  id: number | null,
  options: SWRConfiguration = {}
) => {
  const api = useApi();
  return useSWR<MappingRule>(
    api.isReady() && id !== null ? `/mapping/${id}` : null,
    (url) => api.get(url),
    options
  );
};
