import { TopologyService } from "app/topology/models";
import { useSession } from "next-auth/react";
import useSWR from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { useWebsocket } from "./usePusher";
import { useCallback, useEffect } from "react";
import { toast } from "react-toastify";

const isNullOrUndefined = (value: any) => value === null || value === undefined;

interface TopologyUpdate {
  providerType: string;
  providerId: string;
}

export const useTopology = (
  providerId?: string,
  service?: string,
  environment?: string
) => {
  const { data: session } = useSession();
  useTopologyPolling();
  const apiUrl = getApiURL();

  const url = !session
    ? null
    : !isNullOrUndefined(providerId) &&
      !isNullOrUndefined(service) &&
      !isNullOrUndefined(environment)
    ? `${apiUrl}/topology?provider_id=${providerId}&service_id=${service}&environment=${environment}`
    : `${apiUrl}/topology`;

  const { data, error, mutate } = useSWR<TopologyService[]>(
    url,
    (url: string) => fetcher(url, session!.accessToken)
  );

  return {
    topologyData: data,
    error,
    isLoading: !data && !error,
    mutate,
  };
};

export const useTopologyPolling = () => {
  const { bind, unbind } = useWebsocket();

  const handleIncoming = useCallback((data: TopologyUpdate) => {
    toast.success(
      `Topology pulled from ${data.providerId} (${data.providerType})`,
      { position: "top-right" }
    );
  }, []);

  useEffect(() => {
    bind("topology-update", handleIncoming);
    return () => {
      unbind("topology-update", handleIncoming);
    };
  }, [bind, unbind, handleIncoming]);
};
