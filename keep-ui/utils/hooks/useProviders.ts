import { SWRConfiguration } from "swr";
import { ProvidersResponse } from "@/app/(keep)/providers/providers";
import useSWRImmutable from "swr/immutable";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useProviders = (
  options: SWRConfiguration = { revalidateOnFocus: false }
) => {
  const api = useApi();

  return useSWRImmutable<ProvidersResponse>(
    api.isReady() ? "/providers" : null,
    api.get,
    options
  );
};
