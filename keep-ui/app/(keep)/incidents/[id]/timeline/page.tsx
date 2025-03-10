import { getIncidentName } from "@/entities/incidents/lib/utils";
import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";
import IncidentTimeline from "./incident-timeline";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function IncidentTimelinePage(props: PageProps) {
  const params = await props.params;

  const { id } = params;

  const incident = await getIncidentWithErrorHandling(id);
  return <IncidentTimeline incident={incident} />;
}

export async function generateMetadata(props: PageProps) {
  const params = await props.params;
  const incident = await getIncidentWithErrorHandling(params.id);
  const incidentName = getIncidentName(incident);
  const incidentDescription =
    incident.user_summary || incident.generated_summary;
  return {
    title: `Keep — ${incidentName} — Timeline`,
    description: incidentDescription,
  };
}
