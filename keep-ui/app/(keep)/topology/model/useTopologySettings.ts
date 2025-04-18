import { useApi } from "@/shared/lib/hooks/useApi";
import useSWR, { SWRConfiguration } from "swr";

export interface TopologyProcessorSettings {
  enabled: boolean;
  lookBackWindow: number;
  global_enabled: boolean;
  minimum_services: number;
}

type UseTopologySettingsOptions = {
  initialData?: TopologyProcessorSettings;
  options?: SWRConfiguration;
};

const TOPOLOGY_PROCESSOR_URL = `/topology/settings`;

export const useTopologySettings = ({
  initialData,
  options,
}: UseTopologySettingsOptions = {}) => {
  const api = useApi();

  const { data, error, mutate } = useSWR<TopologyProcessorSettings>(
    api.isReady() ? TOPOLOGY_PROCESSOR_URL : null,
    (url: string) => api.get(url),
    {
      fallbackData: initialData,
      ...options,
    }
  );

  const updateSettings = async (settings: TopologyProcessorSettings) => {
    if (!api.isReady()) return null;
    const response = await api.put<TopologyProcessorSettings>(
      TOPOLOGY_PROCESSOR_URL,
      settings
    );
    await mutate(response);
    return response;
  };

  return {
    settings: data,
    error,
    isLoading: !data && !error,
    updateSettings,
    mutate,
  };
};
