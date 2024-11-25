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
  const baseUrl = `/topology`;

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

export async function getApplications(apiUrl: string, session: Session | null) {
  if (!session) {
    return null;
  }
  const url = `${apiUrl}/topology/applications`;
  return (await fetcher(url, session.accessToken)) as Promise<
    TopologyApplication[]
  >;
}

export function getTopology(
  apiUrl: string,
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
  return fetcher(apiUrl + url, session.accessToken) as Promise<
    TopologyService[]
  >;
}
