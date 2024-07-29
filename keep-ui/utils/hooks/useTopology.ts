import { TopologyService } from "app/topology/models";
import { useSession } from "next-auth/react";
import useSWR from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const useTopology = () => {
  const { data: session } = useSession();
  const apiUrl = getApiURL();

  const { data, error, mutate } = useSWR<TopologyService[]>(
    session ? `${apiUrl}/topology` : null,
    (url: string) => fetcher(url, session!.accessToken)
  );

  return {
    topologyData: data,
    error,
    isLoading: !data && !error,
    mutate,
  };
};
