import { useApi } from "@/shared/lib/hooks/useApi";
import { useApiUrl } from "@/utils/hooks/useConfig";
import useSWR from "swr";

export interface CustomImage {
  provider_name: string;
  id: string;
}

// Cache for blob URLs to prevent memory leaks
const blobCache: Record<string, string> = {};

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

  // Use SWR for image fetching
  const useProviderImage = (providerName: string) => {
    return useSWR(
      providerName ? `/provider-images/${providerName}` : null,
      async () => {
        // Check cache first
        if (blobCache[providerName]) {
          return blobCache[providerName];
        }

        const response = await fetch(
          `${apiUrl}/provider-images/${providerName}`,
          {
            headers: {
              Authorization: `Bearer ${api.getToken()}`,
            },
          }
        );

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        blobCache[providerName] = url;
        return url;
      }
    );
  };

  const getImageUrl = async (providerName: string) => {
    // Check cache first
    if (blobCache[providerName]) {
      return blobCache[providerName];
    }

    const response = await fetch(`${apiUrl}/provider-images/${providerName}`, {
      headers: {
        Authorization: `Bearer ${api.getToken()}`,
      },
    });

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);

    // Store in cache
    blobCache[providerName] = url;

    return url;
  };

  return {
    customImages,
    isLoading,
    error,
    refresh: mutate,
    getImageUrl,
    useProviderImage,
  };
}
