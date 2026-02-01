import { IncidentDto, PaginatedIncidentsDto } from "@/entities/incidents/model";
import { ApiClient } from "@/shared/api";

interface Filters {
  status: string[];
  severity: string[];
  assignees: string[];
  sources: string[];
  affected_services: string[];
}

export type GetIncidentsParams = {
  candidate: boolean;
  limit: number;
  offset: number;
  sorting: { id: string; desc: boolean };
  filters: Filters | {};
  cel?: string;
};

function buildIncidentsUrl(params: GetIncidentsParams) {
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

  if (params.cel) {
    filtersParams.append("cel", params.cel);
  }

  return `/incidents?candidate=${params.candidate}&limit=${params.limit}&offset=${params.offset}&sorting=${
    params.sorting.desc ? "-" : ""
  }${params.sorting.id}&${filtersParams.toString()}`;
}

export async function getIncidents(api: ApiClient, params: GetIncidentsParams) {
  const url = buildIncidentsUrl(params);
  return await api.get<PaginatedIncidentsDto>(url);
}

export async function getIncident(api: ApiClient, id: string) {
  return await api.get<IncidentDto>(`/incidents/${id}`);
}
