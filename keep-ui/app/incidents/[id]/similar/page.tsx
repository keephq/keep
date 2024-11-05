import { SameIncidentsOverview } from "@/features/same-incidents-in-the-past";
import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import { Card } from "@tremor/react";

type PageProps = {
  params: { id: string };
};

export default async function IncidentSimilarPage({
  params: { id },
}: PageProps) {
  const incident = await getIncidentWithErrorHandling(id);
  return (
    <Card>
      <SameIncidentsOverview incident={incident} />
    </Card>
  );
}

export async function generateMetadata({ params }: PageProps) {
  const incident = await getIncidentWithErrorHandling(params.id);
  const incidentName = getIncidentName(incident);
  const incidentDescription =
    incident.user_summary || incident.generated_summary;
  return {
    title: `Keep — ${incidentName} — Similar incidents`,
    description: incidentDescription,
  };
}
