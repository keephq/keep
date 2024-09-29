import { getApiURL } from "../../../utils/apiUrl";
import { fetcher } from "../../../utils/fetcher";
import { Session } from "next-auth";
import { TopologyApplication, TopologyService } from "../model/models";

const isNullOrUndefined = (value: unknown): value is null | undefined =>
  value === null || value === undefined;

export function buildTopologyUrl({
  providerId,
  service,
  environment,
}: {
  providerId?: string;
  service?: string;
  environment?: string;
}) {
  const apiUrl = getApiURL();

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
    providerId,
    service,
    environment,
  }: {
    providerId?: string;
    service?: string;
    environment?: string;
  }
) {
  if (!session) {
    return null;
  }
  const url = buildTopologyUrl({ providerId, service, environment });
  return fetcher(url, session.accessToken) as Promise<TopologyService[]>;
}
