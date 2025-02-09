import useSWR from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";

interface SupersetTokenResponse {
  token: string;
}

export function useSupersetToken() {
  const api = useApi();

  const { data, error, isLoading } = useSWR<SupersetTokenResponse>(
    "/dashboardv2/token",
    async () => {
      const response = await api.get("/dashboardv2/token");
      if (!response?.token) {
        throw new Error("No token in response");
      }
      return response;
    },
    {
      revalidateOnFocus: false,
      revalidateIfStale: false,
      dedupingInterval: 300000,
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
