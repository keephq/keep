import { InternalConfig } from "@/types/internal-config";

export function getApiUrlFromConfig(
  config: InternalConfig | null,
  isServer: boolean = false
) {
  return isServer ? config?.API_URL : config?.API_URL_CLIENT || "/backend";
}
