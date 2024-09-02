import { MaintenanceRule } from "app/maintenance/model";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const useMaintenanceRules = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWR<MaintenanceRule[]>(
    () => (session ? `${apiUrl}/maintenance` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
