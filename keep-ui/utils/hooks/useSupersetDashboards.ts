import useSWR from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";

interface Dashboard {
  id: string;
  uuid: string;
  title: string;
  url: string;
  embed_url: string;
}

interface DashboardsResponse {
  dashboards: Dashboard[];
}

export function useSupersetDashboards() {
  const api = useApi();

  const { data, error, isLoading } = useSWR<DashboardsResponse>(
    "/dashboardv2/dashboards",
    async () => {
      const response = await api.get("/dashboardv2/dashboards");
      if (!response?.dashboards) {
        throw new Error("No dashboards in response");
      }
      return response;
    },
    {
      revalidateOnFocus: false,
      revalidateIfStale: false,
      dedupingInterval: 300000, // 5 minutes
    }
  );

  return {
    dashboards: data?.dashboards || [],
    isLoading,
    error,
  };
}
