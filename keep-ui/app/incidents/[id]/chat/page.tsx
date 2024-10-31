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
  return {
    title: `${incident.user_generated_name} — Chat with AI`,
    description: incident.user_summary || incident.generated_summary,
  };
}
