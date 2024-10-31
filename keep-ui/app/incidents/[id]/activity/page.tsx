import { Card } from "@tremor/react";
import { withIncident, withIncidentMetadata } from "../withIncident";
import dynamic from "next/dynamic";

// Import the client component dynamically with ssr disabled
const IncidentActivity = dynamic(
  () => import("./incident-activity").then((mod) => mod.IncidentActivity),
  { ssr: false } // This ensures the component only renders on client-side
);

const IncidentActivityPage = withIncident(function _IncidentActivityPage({
  incident,
}) {
  return (
    <Card>
      <IncidentActivity incident={incident} />
    </Card>
  );
});

export default IncidentActivityPage;

export const generateMetadata = withIncidentMetadata((incident) => {
  return {
    title: `${incident.user_generated_name} — Activity`,
    description: incident.user_summary || incident.generated_summary,
  };
});
