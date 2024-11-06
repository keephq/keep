import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import useSWRImmutable from "swr/immutable";
import { InternalConfig } from "types/internal-config";
import { fetcher } from "utils/fetcher";

export const useConfig = () => {
  const { data: session } = useSession();

  return useSWRImmutable<InternalConfig>("/api/config", () =>
    fetcher("/api/config", session?.accessToken)
  );
};

export const useApiUrl = () => {
  const { data: config } = useConfig();

  if (config?.API_URL_CLIENT) {
    return config.API_URL_CLIENT;
  }

  // can't access the API directly
  return "/backend";
};
