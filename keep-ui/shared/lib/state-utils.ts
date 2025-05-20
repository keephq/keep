import { useSWRConfig } from "swr";
import { useCallback } from "react";

/**
 * Custom hook that provides a function to revalidate multiple SWR cache entries at once
 * 
 * @returns A function that revalidates SWR cache entries based on provided keys
 * 
 * @example
 * // Basic usage
 * const revalidateMultiple = useRevalidateMultiple();
 * 
 * // Revalidate all cache entries that start with these prefixes
 * revalidateMultiple(['/api/alerts', '/api/workflows']);
 * 
 * // Revalidate only exact matches
 * revalidateMultiple(['/api/alerts/123', '/api/workflows/456'], { isExact: true });
 */
export const useRevalidateMultiple = () => {
  const { mutate } = useSWRConfig();
  return useCallback(
    /**
     * Revalidates multiple SWR cache entries based on provided keys
     * 
     * @param keys - Array of cache keys or key prefixes to revalidate
     * @param options - Configuration options
     * @param options.isExact - When true, matches keys exactly; when false, matches keys that start with the provided prefixes
     */
    (keys: string[], options: { isExact: boolean } = { isExact: false }) => {
      console.log("revalidating", keys, options);
      mutate(
        (key) =>
          typeof key === "string" &&
          keys.some((k) => (options.isExact ? k === key : key.startsWith(k)))
      );
    },
    [mutate]
  );
};
