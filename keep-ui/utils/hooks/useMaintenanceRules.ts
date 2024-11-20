import { MaintenanceRule } from "app/maintenance/model";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import useSWR, { SWRConfiguration } from "swr";
import { useApiUrl } from "./useConfig";
import { fetcher } from "utils/fetcher";

export const useMaintenanceRules = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  return useSWR<MaintenanceRule[]>(
    () => (session ? `${apiUrl}/maintenance` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
