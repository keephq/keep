import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";
import IncidentWorkflowTable from "./incident-workflow-table";

type PageProps = {
  params: { id: string };
};

export default async function IncidentWorkflowsPage({
  params: { id },
}: PageProps) {
  const incident = await getIncidentWithErrorHandling(id);
  return <IncidentWorkflowTable incident={incident} />;
}

export async function generateMetadata({ params }: PageProps) {
  const incident = await getIncidentWithErrorHandling(params.id);
  return {
    title: `${incident.user_generated_name} — Workflows`,
    description: incident.user_summary || incident.generated_summary,
  };
}
