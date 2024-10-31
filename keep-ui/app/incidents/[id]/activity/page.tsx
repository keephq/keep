import { Card } from "@tremor/react";
import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";
import dynamic from "next/dynamic";
import { Metadata } from "next";

// Import the client component dynamically with ssr disabled
const IncidentActivity = dynamic(
  () => import("./incident-activity").then((mod) => mod.IncidentActivity),
  { ssr: false } // This ensures the component only renders on client-side
);

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
  return {
    title: `${incident.user_generated_name} — Activity`,
    description: incident.user_summary || incident.generated_summary,
  };
}
