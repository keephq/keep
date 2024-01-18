import useSWR from "swr";
import { InternalConfig } from "types/internal-config";
import { fetcher } from "utils/fetcher";

export const useConfig = () => {
  return useSWR<InternalConfig>("/api/config", fetcher);
};
