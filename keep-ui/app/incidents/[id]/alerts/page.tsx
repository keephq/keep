import { Card } from "@tremor/react";
import IncidentOverview from "./incident-overview";
import IncidentAlerts from "./incident-alerts";
import { withIncident, withIncidentMetadata } from "../withIncident";

const IncidentAlertsPage = withIncident(function _IncidentAlertsPage({
  incident,
}) {
  return (
    <>
      <Card className="mb-4">
        <IncidentOverview incident={incident} />
      </Card>
      <IncidentAlerts incident={incident} />
    </>
  );
});

export default IncidentAlertsPage;

export const generateMetadata = withIncidentMetadata((incident) => {
  return {
    title: `${incident.user_generated_name} — Alerts`,
    description: incident.user_summary || incident.generated_summary,
  };
});
