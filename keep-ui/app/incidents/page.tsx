import Incident from "./incident";
import {
  defaultPagination,
  defaultSorting,
  fetchIncidents,
} from "@/app/incidents/api";
import { getServerSession } from "next-auth/next";
import { authOptions } from "@/pages/api/auth/[...nextauth]";

export default async function Page() {
  const session = await getServerSession(authOptions);
  const incidents = await fetchIncidents(
    session,
    true,
    defaultPagination.limit,
    defaultPagination.offset,
    defaultSorting[0]
  );
  const predictedIncidents = await fetchIncidents(session, false);
  return (
    <Incident
      initialIncidents={incidents}
      initialPredictedIncidents={predictedIncidents}
    />
  );
}

export const metadata = {
  title: "Keep - Incidents",
  description: "List of incidents",
};
