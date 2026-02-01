import { ExtractionRule } from "@/app/(keep)/extraction/model";
import useSWR, { SWRConfiguration } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useExtractions = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();

  return useSWR<ExtractionRule[]>(
    api.isReady() ? "/extraction" : null,
    (url) => api.get(url),
    options
  );
};
