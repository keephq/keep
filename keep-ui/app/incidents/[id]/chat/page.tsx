import { IncidentChatClientPage } from "./page.client";
import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";
import { getIncidentName } from "@/entities/incidents/lib/utils";

type PageProps = {
  params: { id: string };
};

export default async function IncidentChatPage({ params: { id } }: PageProps) {
  const incident = await getIncidentWithErrorHandling(id);
  return <IncidentChatClientPage incident={incident} />;
}

export async function generateMetadata({ params }: PageProps) {
  const incident = await getIncidentWithErrorHandling(params.id);
  const incidentName = getIncidentName(incident);
  const incidentDescription =
    incident.user_summary || incident.generated_summary;
  return {
    title: `Keep — ${incidentName} — Chat with AI`,
    description: incidentDescription,
  };
}
