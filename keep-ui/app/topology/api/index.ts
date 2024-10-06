import { getApiURL } from "@/utils/apiUrl";
import { fetcher } from "@/utils/fetcher";
import { Session } from "next-auth";
import { TopologyApplication, TopologyService } from "../model/models";

export function buildTopologyUrl({
  providerIds,
  services,
  environment,
}: {
  providerIds?: string[];
  services?: string[];
  environment?: string;
}) {
  const apiUrl = getApiURL();

  const baseUrl = `${apiUrl}/topology`;

  const params = new URLSearchParams();

  if (providerIds) {
    params.append("provider_ids", providerIds.join(","));
  }
  if (services) {
    params.append("services", services.join(","));
  }
  if (environment) {
    params.append("environment", environment);
  }

  return `${baseUrl}?${params.toString()}`;
}

export async function getApplications(session: Session | null) {
  if (!session) {
    return null;
  }
  const apiUrl = `${getApiURL()}/topology/applications`;
  return (await fetcher(apiUrl, session.accessToken)) as Promise<
    TopologyApplication[]
  >;
}

export function getTopology(
  session: Session | null,
  {
    providerIds,
    services,
    environment,
  }: {
    providerIds?: string[];
    services?: string[];
    environment?: string;
  }
) {
  if (!session) {
    return null;
  }
  const url = buildTopologyUrl({ providerIds, services, environment });
  return fetcher(url, session.accessToken) as Promise<TopologyService[]>;
}
