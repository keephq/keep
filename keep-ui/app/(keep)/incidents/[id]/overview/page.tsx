// keep-ui/app/(keep)/incidents/[id]/overview/page.tsx

import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import { Metadata } from "next";
import OverviewClientPage from "./overview-client";

type PageProps = {
  params: { id: string };
};

export default async function Page({ params: { id } }: PageProps) {
  const incident = await getIncidentWithErrorHandling(id);
  return <OverviewClientPage initialIncident={incident} />;
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const incident = await getIncidentWithErrorHandling(params.id);
  const incidentName = getIncidentName(incident);
  return {
    title: `Keep — ${incidentName} — Overview`,
    description: incident.user_summary || incident.generated_summary,
  };
}
