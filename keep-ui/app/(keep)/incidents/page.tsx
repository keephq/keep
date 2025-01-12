import { IncidentList } from "@/features/incident-list";
import { getIncidents, GetIncidentsParams } from "@/entities/incidents/api";
import { PaginatedIncidentsDto } from "@/entities/incidents/model";
import { createServerApiClient } from "@/shared/api/server";
import {DefaultIncidentFilters} from "@/entities/incidents/model/models";
import { getInitialFacets, InitialFacetsData } from "@/features/filter/api";

const defaultIncidentsParams: GetIncidentsParams = {
  confirmed: true,
  limit: 20,
  offset: 0,
  sorting: { id: "creation_time", desc: true },
  filters: DefaultIncidentFilters,
};

export default async function Page() {
  let incidents: PaginatedIncidentsDto | null = null;
  let facetsData: InitialFacetsData | null = null;

  try {
    const api = await createServerApiClient();

    const tasks = [
      getIncidents(api, defaultIncidentsParams),
      getInitialFacets(api, "incidents"),
    ]
    const [_incidents, _facetsData] = await Promise.all(tasks);
    incidents = _incidents as PaginatedIncidentsDto;
    facetsData = _facetsData as InitialFacetsData;

  } catch (error) {
    console.log(error);
  }
  return <IncidentList initialData={incidents ?? undefined} initialFacetsData={facetsData ?? undefined} />;
}

export const metadata = {
  title: "Keep - Incidents",
  description: "List of incidents",
};
