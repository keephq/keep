import { TopologyApplication, TopologyService } from "../model/models";
import { ApiClient } from "@/shared/lib/api/ApiClient";

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

export async function getApplications(api: ApiClient) {
  const url = `/topology/applications`;
  return (await api.get(url)) as Promise<TopologyApplication[]>;
}

export async function getTopology(
  api: ApiClient,
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
  const url = buildTopologyUrl({ providerIds, services, environment });
  return (await api.get(url)) as Promise<TopologyService[]>;
}
