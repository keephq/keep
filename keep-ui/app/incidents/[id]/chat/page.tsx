import { IncidentChatClientPage } from "./page.client";
import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";

type PageProps = {
  params: { id: string };
};

export default async function IncidentChatPage({ params: { id } }: PageProps) {
  const incident = await getIncidentWithErrorHandling(id);
  return <IncidentChatClientPage incident={incident} />;
}

export async function generateMetadata({ params }: PageProps) {
  const incident = await getIncidentWithErrorHandling(params.id);
  const incidentName =
    incident.user_generated_name || incident.ai_generated_name;
  const incidentDescription =
    incident.user_summary || incident.generated_summary;
  return {
    title: `${incidentName} — Chat with AI`,
    description: incidentDescription,
  };
}
