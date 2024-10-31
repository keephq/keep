import { withIncident, withIncidentMetadata } from "../withIncident";
import IncidentWorkflowTable from "./incident-workflow-table";

const IncidentWorkflowsPage = withIncident(function _IncidentWorkflowsPage({
  incident,
}) {
  return <IncidentWorkflowTable incident={incident} />;
});

export default IncidentWorkflowsPage;

export const generateMetadata = withIncidentMetadata((incident) => {
  return {
    title: `${incident.user_generated_name} — Workflows`,
    description: incident.user_summary || incident.generated_summary,
  };
});
