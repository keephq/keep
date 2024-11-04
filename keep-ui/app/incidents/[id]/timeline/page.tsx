import { getIncidentName } from "@/entities/incidents/lib/utils";
import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";
import IncidentTimeline from "./incident-timeline";

type PageProps = {
  params: { id: string };
};

export default async function IncidentTimelinePage({
  params: { id },
}: PageProps) {
  const incident = await getIncidentWithErrorHandling(id);
  return <IncidentTimeline incident={incident} />;
}

export async function generateMetadata({ params }: PageProps) {
  const incident = await getIncidentWithErrorHandling(params.id);
  const incidentName = getIncidentName(incident);
  const incidentDescription =
    incident.user_summary || incident.generated_summary;
  return {
    title: `Keep — ${incidentName} — Timeline`,
    description: incidentDescription,
  };
}
