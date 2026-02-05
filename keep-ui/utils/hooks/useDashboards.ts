import useSWR from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";

export interface Dashboard {
  id: string;
  dashboard_name: string;
  dashboard_config: any;
}

export const useDashboards = () => {
  const api = useApi();

  const { data, error, mutate } = useSWR<Dashboard[]>(
    api.isReady() ? "/dashboard" : null,
    (url: string) => api.get(url),
    {
      revalidateOnFocus: false,
    }
  );

  return {
    dashboards: data,
    error,
    isLoading: !data && !error,
    mutate,
  };
};
