import { IncidentDto, PaginatedIncidentsDto } from "@/entities/incidents/model";
import { fetcher } from "@/utils/fetcher";
import { Session } from "next-auth";

interface Filters {
  status: string[];
  severity: string[];
  assignees: string[];
  sources: string[];
  affected_services: string[];
}

export type GetIncidentsParams = {
  confirmed: boolean;
  limit: number;
  offset: number;
  sorting: { id: string; desc: boolean };
  filters: Filters | {};
};

export function buildIncidentsUrl(apiUrl: string, params: GetIncidentsParams) {
  const filtersParams = new URLSearchParams();

  Object.entries(params.filters).forEach(([key, value]) => {
    if (value.length == 0) {
      filtersParams.delete(key as string);
    } else {
      value.forEach((s: string) => {
        filtersParams.append(key, s);
      });
    }
  });

  return `${apiUrl}/incidents?confirmed=${params.confirmed}&limit=${params.limit}&offset=${params.offset}&sorting=${
    params.sorting.desc ? "-" : ""
  }${params.sorting.id}&${filtersParams.toString()}`;
}

export async function getIncidents(
  apiUrl: string,
  session: Session | null,
  params: GetIncidentsParams
) {
  if (!session) {
    return null;
  }
  const url = buildIncidentsUrl(apiUrl, params);
  return (await fetcher(
    url,
    session.accessToken
  )) as Promise<PaginatedIncidentsDto>;
}

export async function getIncident(
  apiUrl: string,
  session: Session | null,
  id: string
) {
  const url = `${apiUrl}/incidents/${id}`;
  // enabling caching to avoid duplicate requests for incident metadata
  return (await fetcher(url, session?.accessToken, {
    headers: {
      cache: "force-cache",
    },
  })) as IncidentDto;
}
