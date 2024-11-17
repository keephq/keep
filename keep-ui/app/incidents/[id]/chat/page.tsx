import { IncidentChatClientPage } from "./page.client";
import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";
import { getIncidentName } from "@/entities/incidents/lib/utils";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function IncidentChatPage(props: PageProps) {
  const params = await props.params;

  const {
    id
  } = params;

  const incident = await getIncidentWithErrorHandling(id);
  return <IncidentChatClientPage incident={incident} />;
}

export async function generateMetadata(props: PageProps) {
  const params = await props.params;
  const incident = await getIncidentWithErrorHandling(params.id);
  const incidentName = getIncidentName(incident);
  const incidentDescription =
    incident.user_summary || incident.generated_summary;
  return {
    title: `Keep — ${incidentName} — Chat with AI`,
    description: incidentDescription,
  };
}
