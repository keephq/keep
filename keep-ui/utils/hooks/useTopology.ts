import { TopologyService, Application } from "app/topology/models";
import { useSession } from "next-auth/react";
import type { Session } from "next-auth";
import useSWR from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { useWebsocket } from "./usePusher";
import { useCallback, useEffect } from "react";
import { toast } from "react-toastify";
import { useApplications } from "./useApplications";

const isNullOrUndefined = (value: unknown): value is null | undefined =>
  value === null || value === undefined;

function buildTopologyUrl({
  providerId,
  service,
  environment,
  session,
}: {
  providerId?: string;
  service?: string;
  environment?: string;
  session: Session | null;
}) {
  const apiUrl = getApiURL();

  if (!session) {
    return null;
  }

  const baseUrl = `${apiUrl}/topology`;

  if (
    !isNullOrUndefined(providerId) &&
    !isNullOrUndefined(service) &&
    !isNullOrUndefined(environment)
  ) {
    const params = new URLSearchParams({
      provider_id: providerId,
      service_id: service,
      environment: environment,
    });
    return `${baseUrl}?${params.toString()}`;
  }

  return baseUrl;
}

interface TopologyUpdate {
  providerType: string;
  providerId: string;
}

// TODO: ensure that hook is memoized so could be used multiple times in the tree without rerenders
export const useTopology = (
  providerId?: string,
  service?: string,
  environment?: string
) => {
  const { data: session } = useSession();

  useTopologyPolling();

  const url = buildTopologyUrl({ session, providerId, service, environment });

  const { data, error, mutate } = useSWR<TopologyService[]>(
    url,
    (url: string) => fetcher(url, session!.accessToken)
  );

  const { applications } = useApplications();

  // TODO: remove once endpoint returns application data
  if (data) {
    const dataWithApplications = data.map((service) => {
      const application = applications.find((application) =>
        application.services.some((s) => s.id === service.service.toString())
      );
      return {
        ...service,
        applicationObject: application,
      };
    });

    return {
      topologyData: dataWithApplications,
      error,
      isLoading: !data && !error,
      mutate,
    };
  }

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
