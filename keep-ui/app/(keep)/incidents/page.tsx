import { IncidentList } from "@/features/incident-list";
import { getIncidents, GetIncidentsParams } from "@/entities/incidents/api";
import { PaginatedIncidentsDto } from "@/entities/incidents/model";
import { createServerApiClient } from "@/shared/api/server";
import {DefaultIncidentFilters} from "@/entities/incidents/model/models";

const defaultIncidentsParams: GetIncidentsParams = {
  confirmed: true,
  limit: 20,
  offset: 0,
  sorting: { id: "creation_time", desc: true },
  filters: DefaultIncidentFilters,
};

export default async function Page() {
  let incidents: PaginatedIncidentsDto | null = null;
  try {
    const api = await createServerApiClient();
    incidents = await getIncidents(api, defaultIncidentsParams);
  } catch (error) {
    console.log(error);
  }
  return <IncidentList initialData={incidents ?? undefined} />;
}

export const metadata = {
  title: "Keep - Incidents",
  description: "List of incidents",
};
