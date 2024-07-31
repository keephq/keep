import { TopologyService } from "app/topology/models";
import { useSession } from "next-auth/react";
import useSWR from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

const isNullOrUndefined = (value: any) => value === null || value === undefined;

export const useTopology = (
  providerId?: string,
  service?: string,
  environment?: string
) => {
  const { data: session } = useSession();
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
