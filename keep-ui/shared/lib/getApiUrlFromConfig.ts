import { InternalConfig } from "@/types/internal-config";

/**
 * Extracts the API URL from the application configuration
 * 
 * @param config - The application's internal configuration object
 * @returns The configured API URL or the default "/backend" if not specified
 * 
 * @example
 * const apiUrl = getApiUrlFromConfig(config);
 * fetch(`${apiUrl}/alerts`);
 */
export function getApiUrlFromConfig(config: InternalConfig | null) {
  return config?.API_URL_CLIENT || "/backend";
}
