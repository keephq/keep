import { Metadata } from "next";
import { Card } from "@tremor/react";
import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";
import { IncidentActivity } from "./incident-activity";
import { getIncidentName } from "@/entities/incidents/lib/utils";

export default async function IncidentActivityPage({
  params: { id },
}: {
  params: { id: string };
}) {
  const incident = await getIncidentWithErrorHandling(id);
  return (
    <Card>
      <IncidentActivity incident={incident} />
    </Card>
  );
}

export async function generateMetadata({
  params,
}: {
  params: { id: string };
}): Promise<Metadata> {
  const incident = await getIncidentWithErrorHandling(params.id);
  const incidentName = getIncidentName(incident);
  return {
    title: `Keep — ${incidentName} — Activity`,
    description: incident.user_summary || incident.generated_summary,
  };
}
