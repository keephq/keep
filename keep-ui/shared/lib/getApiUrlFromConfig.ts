import { InternalConfig } from "@/types/internal-config";

export function getApiUrlFromConfig(config: InternalConfig | null) {
  return config?.API_URL_CLIENT || "/backend";
}
