import { getIncidentName } from "@/entities/incidents/lib/utils";
import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";
import IncidentWorkflowTable from "./incident-workflow-table";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function IncidentWorkflowsPage(props: PageProps) {
  const params = await props.params;

  const {
    id
  } = params;

  const incident = await getIncidentWithErrorHandling(id);
  return <IncidentWorkflowTable incident={incident} />;
}

export async function generateMetadata(props: PageProps) {
  const params = await props.params;
  const incident = await getIncidentWithErrorHandling(params.id);
  const incidentName = getIncidentName(incident);
  const incidentDescription =
    incident.user_summary || incident.generated_summary;
  return {
    title: `Keep — ${incidentName} — Workflows`,
    description: incidentDescription,
  };
}
