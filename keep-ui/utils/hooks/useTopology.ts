import { TopologyService } from "app/topology/models";
import { useSession } from "next-auth/react";
import useSWR from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { useWebsocket } from "./usePusher";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "react-toastify";
import { buildTopologyUrl } from "../../app/topology/data/api";

export const topologyBaseKey = `${getApiURL()}/topology`;

interface TopologyUpdate {
  providerType: string;
  providerId: string;
}

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
  const __debug__prevData = useRef<TopologyService[] | null | undefined>(null);
  const { data: session } = useSession();
  const { data: pollTopology } = useTopologyPolling();

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

  // useEffect(
  //   function __debug__dataChanged() {
  //     console.log("data changed", data);
  //     if (__debug__prevData.current) {
  //       console.log("prevData", __debug__prevData.current);
  //     }
  //     __debug__prevData.current = data;
  //   },
  //   [data]
  // );

  return {
    topologyData: data,
    error,
    isLoading: !data && !error,
    mutate,
  };
};

export const useTopologyPolling = () => {
  const { bind, unbind } = useWebsocket();
  const [pollTopology, setPollTopology] = useState(0);

  const handleIncoming = useCallback((data: TopologyUpdate) => {
    toast.success(
      `Topology pulled from ${data.providerId} (${data.providerType})`,
      { position: "top-right" }
    );
    setPollTopology(Math.floor(Math.random() * 10000));
  }, []);

  useEffect(() => {
    bind("topology-update", handleIncoming);
    return () => {
      unbind("topology-update", handleIncoming);
    };
  }, [bind, unbind, handleIncoming]);

  return { data: pollTopology };
};
