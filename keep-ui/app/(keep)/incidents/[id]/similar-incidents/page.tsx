import SimilarIncidentsTable from "./similar-incidents";
import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";
import { getIncidentName } from "@/entities/incidents/lib/utils";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function IncidentAlertsByRunPage(props: PageProps) {
  const params = await props.params;

  const { id } = params;
  return <SimilarIncidentsTable id={id} />;
}

export async function generateMetadata(props: PageProps) {
  const params = await props.params;
  const incident = await getIncidentWithErrorHandling(params.id);
  const incidentName = getIncidentName(incident);
  const incidentDescription =
    incident.user_summary || incident.generated_summary;
  return {
    title: `Vina — ${incidentName} — Similar Incidents`,
    description: incidentDescription,
  };
}
