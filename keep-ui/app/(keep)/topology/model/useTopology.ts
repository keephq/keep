import { TopologyService } from "@/app/(keep)/topology/model/models";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import useSWR, { SWRConfiguration } from "swr";
import { fetcher } from "@/utils/fetcher";
import { useEffect } from "react";
import { buildTopologyUrl } from "@/app/(keep)/topology/api";
import { useTopologyPollingContext } from "@/app/(keep)/topology/model/TopologyPollingContext";
import { useApiUrl } from "utils/hooks/useConfig";

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
  const { data: session } = useSession();
  const apiUrl = useApiUrl();
  const pollTopology = useTopologyPollingContext();

  const url = !session
    ? null
    : buildTopologyUrl({ providerIds, services, environment });

  const { data, error, mutate } = useSWR<TopologyService[]>(
    url,
    (url: string) => fetcher(apiUrl! + url, session!.accessToken),
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
