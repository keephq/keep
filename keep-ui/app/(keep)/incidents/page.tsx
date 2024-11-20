import { getApiURL } from "@/utils/apiUrl";
import { auth } from "@/auth";
import { IncidentList } from "@/features/incident-list";
import {
  getIncidents,
  GetIncidentsParams,
} from "@/entities/incidents/api/incidents";
import { PaginatedIncidentsDto } from "@/entities/incidents/model";

const defaultIncidentsParams: GetIncidentsParams = {
  confirmed: true,
  limit: 20,
  offset: 0,
  sorting: { id: "creation_time", desc: true },
  filters: {},
};

export default async function Page() {
  let incidents: PaginatedIncidentsDto | null = null;
  try {
    const session = await auth();
    const apiUrl = getApiURL();

    incidents = await getIncidents(apiUrl, session, defaultIncidentsParams);
  } catch (error) {
    console.log(error);
  }
  return <IncidentList initialData={incidents ?? undefined} />;
}

export const metadata = {
  title: "Keep - Incidents",
  description: "List of incidents",
};
