import { IncidentList } from "@/features/incident-list";
import { getIncidents, GetIncidentsParams } from "@/entities/incidents/api";
import { PaginatedIncidentsDto } from "@/entities/incidents/model";
import { createServerApiClient } from "@/shared/api/server";
import { DefaultIncidentFilters } from "@/entities/incidents/model/models";
import { getInitialFacets } from "@/features/filter/api";
import { FacetDto } from "@/features/filter";

const defaultIncidentsParams: GetIncidentsParams = {
  confirmed: true,
  limit: 20,
  offset: 0,
  sorting: { id: "creation_time", desc: true },
  filters: DefaultIncidentFilters,
  cel: "!(status in ['resolved', 'deleted'])", // on initial page load, we have to display only active incidents
};

export default async function Page() {
  let incidents: PaginatedIncidentsDto | null = null;
  let initialFacets: FacetDto[] | null = null;

  try {
    const api = await createServerApiClient();

    const tasks = [
      getIncidents(api, defaultIncidentsParams),
      await getInitalFacets(api, "incidents"),
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
