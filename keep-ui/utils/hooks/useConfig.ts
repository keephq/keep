import useSWRImmutable from "swr/immutable";
import { InternalConfig } from "types/internal-config";
import { fetcher } from "utils/fetcher";

export const useConfig = () => {
  return useSWRImmutable<InternalConfig>("/api/config", fetcher, {
    revalidateOnFocus: false,
    revalidateOnMount: false,
    revalidateIfStale: false,
  });
};
