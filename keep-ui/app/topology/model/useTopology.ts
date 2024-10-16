import { TopologyService } from "@/app/topology/model/models";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "@/utils/apiUrl";
import { fetcher } from "@/utils/fetcher";
import { useEffect } from "react";
import { buildTopologyUrl } from "@/app/topology/api";
import { useTopologyPollingContext } from "@/app/topology/model/TopologyPollingContext";

export const topologyBaseKey = `${getApiURL()}/topology`;

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
  const pollTopology = useTopologyPollingContext();

  const url = !session
    ? null
    : buildTopologyUrl({ providerIds, services, environment });

  const { data, error, mutate } = useSWR<TopologyService[]>(
    url,
    (url: string) => fetcher(url, session!.accessToken),
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
