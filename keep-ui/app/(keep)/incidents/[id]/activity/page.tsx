import { Metadata } from "next";
import { Card } from "@tremor/react";
import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";
import { IncidentActivity } from "./incident-activity";
import { getIncidentName } from "@/entities/incidents/lib/utils";

export default async function IncidentActivityPage(props: {
  params: Promise<{ id: string }>;
}) {
  const params = await props.params;

  const { id } = params;

  const incident = await getIncidentWithErrorHandling(id);
  return (
    <Card>
      <IncidentActivity incident={incident} />
    </Card>
  );
}

export async function generateMetadata(props: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const params = await props.params;
  const incident = await getIncidentWithErrorHandling(params.id);
  const incidentName = getIncidentName(incident);
  return {
    title: `Keep — ${incidentName} — Activity`,
    description: incident.user_summary || incident.generated_summary,
  };
}
