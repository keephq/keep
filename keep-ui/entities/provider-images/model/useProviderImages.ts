import { useApi } from "@/shared/lib/hooks/useApi";
import { useApiUrl } from "@/utils/hooks/useConfig";
import useSWR from "swr";

export interface CustomImage {
  provider_name: string;
  id: string;
}

export function useProviderImages() {
  const api = useApi();
  const apiUrl = useApiUrl();

  const {
    data: customImages,
    isLoading,
    error,
    mutate,
  } = useSWR<CustomImage[]>("/provider-images", async () => {
    const response = await api.get("/provider-images");
    return response;
  });

  // Add a function to get authenticated image URL
  const getImageUrl = async (providerName: string) => {
    const response = await fetch(`${apiUrl}/provider-images/${providerName}`, {
      headers: {
        Authorization: `Bearer ${api.getToken()}`,
      },
    });

    const blob = await response.blob();
    return URL.createObjectURL(blob);
  };

  return {
    customImages,
    isLoading,
    error,
    refresh: mutate,
    getImageUrl,
  };
}
