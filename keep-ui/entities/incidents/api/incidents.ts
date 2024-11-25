import { IncidentDto, PaginatedIncidentsDto } from "@/entities/incidents/model";
import { ApiClient } from "@/shared/lib/api/ApiClient";

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

export function buildIncidentsUrl(params: GetIncidentsParams) {
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

  return `/incidents?confirmed=${params.confirmed}&limit=${params.limit}&offset=${params.offset}&sorting=${
    params.sorting.desc ? "-" : ""
  }${params.sorting.id}&${filtersParams.toString()}`;
}

export async function getIncidents(api: ApiClient, params: GetIncidentsParams) {
  const url = buildIncidentsUrl(params);
  return (await api.get(url)) as Promise<PaginatedIncidentsDto>;
}

export async function getIncident(api: ApiClient, id: string) {
  return (await api.get(`/incidents/${id}`)) as IncidentDto;
}
