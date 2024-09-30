import { TopologyService } from "@/app/topology/model/models";
import { useSession } from "next-auth/react";
import useSWR from "swr";
import { getApiURL } from "../../../utils/apiUrl";
import { fetcher } from "../../../utils/fetcher";
import { useEffect } from "react";
import { buildTopologyUrl } from "@/app/topology/api";
import { useTopologyPollingContext } from "@/app/topology/model/TopologyPollingContext";

export const topologyBaseKey = `${getApiURL()}/topology`;

type UseTopologyOptions = {
  providerId?: string;
  service?: string;
  environment?: string;
  initialData?: TopologyService[];
};

// TODO: ensure that hook is memoized so could be used multiple times in the tree without rerenders
export const useTopology = ({
  providerId,
  service,
  environment,
  initialData: fallbackData,
}: UseTopologyOptions = {}) => {
  const { data: session } = useSession();
  const pollTopology = useTopologyPollingContext();

  const url = !session
    ? null
    : buildTopologyUrl({ providerId, service, environment });

  const { data, error, mutate } = useSWR<TopologyService[]>(
    url,
    (url: string) => fetcher(url, session!.accessToken),
    {
      fallbackData,
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
