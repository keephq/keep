import useSWR from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";

interface SupersetTokenResponse {
  token: string;
}

interface UseSupersetTokenProps {
  dashboardId: string;
}

export function useSupersetToken({ dashboardId }: UseSupersetTokenProps) {
  const api = useApi();

  const { data, error, isLoading } = useSWR<SupersetTokenResponse>(
    dashboardId ? `/dashboardv2/token?dashboard_id=${dashboardId}` : null,
    async () => {
      const response = await api.get(
        `/dashboardv2/token?dashboard_id=${dashboardId}`
      );
      if (!response?.token) {
        throw new Error("No token in response");
      }
      return response;
    },
    {
      revalidateOnFocus: false,
      revalidateIfStale: false,
      dedupingInterval: 300000, // 5 minutes
    }
  );

  const fetchToken = async (): Promise<string> => {
    if (!data?.token) {
      throw new Error("Token not available");
    }
    return data.token;
  };

  return {
    fetchToken,
    isLoading,
    error,
    token: data?.token,
  };
}
