import { MaintenanceRule } from "@/app/(keep)/maintenance/model";
import useSWR, { SWRConfiguration } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useMaintenanceRules = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();

  return useSWR<MaintenanceRule[]>(
    api.isReady() ? "/maintenance" : null,
    api.get,
    options
  );
};
