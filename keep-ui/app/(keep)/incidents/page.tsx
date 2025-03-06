import { IncidentList } from "@/features/incident-list";
import { getIncidents, GetIncidentsParams } from "@/entities/incidents/api";
import { PaginatedIncidentsDto } from "@/entities/incidents/model";
import { createServerApiClient } from "@/shared/api/server";
import {
  DEFAULT_INCIDENTS_CEL,
  DefaultIncidentFilters,
  DEFAULT_INCIDENTS_PAGE_SIZE,
  DEFAULT_INCIDENTS_SORTING,
} from "@/entities/incidents/model/models";
import { getInitialFacets } from "@/features/filter/api";
import { FacetDto } from "@/features/filter";

const defaultIncidentsParams: GetIncidentsParams = {
  confirmed: true,
  limit: DEFAULT_INCIDENTS_PAGE_SIZE,
  offset: 0,
  sorting: DEFAULT_INCIDENTS_SORTING,
  filters: DefaultIncidentFilters,
  cel: DEFAULT_INCIDENTS_CEL,
};

export default async function Page() {
  let incidents: PaginatedIncidentsDto | null = null;
  let initialFacets: FacetDto[] | null = null;

  try {
    const api = await createServerApiClient();

    const tasks = [
      getIncidents(api, defaultIncidentsParams),
      getInitialFacets(api, "incidents"),
    ];
    const [_incidents, _facetsData] = await Promise.all(tasks);
    incidents = _incidents as PaginatedIncidentsDto;
    initialFacets = _facetsData as FacetDto[];
  } catch (error) {
    console.log(error);
  }
  return (
    <IncidentList
      initialData={incidents ?? undefined}
      initialFacetsData={
        initialFacets
          ? { facets: initialFacets, facetOptions: null }
          : undefined
      }
    />
  );
}

export const metadata = {
  title: "Keep - Incidents",
  description: "List of incidents",
};
