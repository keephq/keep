import { useApi } from "@/shared/lib/hooks/useApi";
import { useApiUrl } from "@/utils/hooks/useConfig";
import useSWRImmutable from "swr";

export interface CustomImage {
  provider_name: string;
  id: string;
}

// Cache for blob URLs to prevent memory leaks
const blobCache: Record<string, string> = {};
// Cache for in-flight requests to prevent duplicate fetches
const requestCache: Record<string, Promise<string>> = {};

export function useProviderImages() {
  const api = useApi();
  const apiUrl = useApiUrl();

  const {
    data: customImages,
    isLoading,
    error,
    mutate,
  } = useSWRImmutable<CustomImage[]>(
    "/provider-images",
    async () => {
      const response = await api.get("/provider-images");
      return response;
    },
    {
      revalidateOnFocus: false,
      revalidateOnMount: false,
      revalidateOnReconnect: false,
      revalidateIfStale: false,
    }
  );

  // Use SWR for image fetching
  const useProviderImage = (providerName: string) => {
    return useSWRImmutable(
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
    // Check blob cache first
    if (blobCache[providerName]) {
      return blobCache[providerName];
    }

    // Check if there's already a request in flight
    if (providerName in requestCache) {
      return requestCache[providerName];
    }

    // Create new request promise and store in cache
    requestCache[providerName] = fetch(
      `${apiUrl}/provider-images/${providerName}`,
      {
        headers: {
          Authorization: `Bearer ${api.getToken()}`,
        },
      }
    )
      .then((response) => response.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        blobCache[providerName] = url;
        delete requestCache[providerName];
        return url;
      })
      .catch((error) => {
        delete requestCache[providerName];
        throw error;
      });

    return requestCache[providerName];
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
