import { TopologyService } from "@/app/(keep)/topology/model/models";
import useSWR, { SWRConfiguration } from "swr";
import { useEffect } from "react";
import { buildTopologyUrl } from "@/app/(keep)/topology/api";
import { useTopologyPollingContext } from "@/app/(keep)/topology/model/TopologyPollingContext";
import { useApiUrl } from "utils/hooks/useConfig";
import { useApi } from "@/shared/lib/hooks/useApi";

export const TOPOLOGY_URL = `/topology`;

type UseTopologyOptions = {
  providerIds?: string[];
  services?: string[];
  environment?: string;
  initialData?: TopologyService[];
  options?: SWRConfiguration;
};

// TODO: ensure that hook is memoized so could be used multiple times in the tree without rerenders
export const useTopology = (
  {
    providerIds,
    services,
    environment,
    initialData: fallbackData,
    options,
  }: UseTopologyOptions = {
    options: {
      revalidateOnFocus: false,
    },
  }
) => {
  const api = useApi();
  const pollTopology = useTopologyPollingContext();

  const url = api.isReady()
    ? null
    : buildTopologyUrl({ providerIds, services, environment });

  const { data, error, mutate } = useSWR<TopologyService[]>(
    url,
    (url: string) => api.get(url),
    {
      fallbackData,
      ...options,
    }
  );

  useEffect(() => {
    if (pollTopology) {
      mutate();
      console.log("mutate triggered because of pollTopology");
    }
  }, [pollTopology, mutate]);

  return {
    topologyData: data,
    error,
    isLoading: !data && !error,
    mutate,
  };
};
