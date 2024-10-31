import { withIncident, withIncidentMetadata } from "../withIncident";
import IncidentTimeline from "./incident-timeline";

const IncidentTimelinePage = withIncident(function _IncidentTimelinePage({
  incident,
}) {
  return <IncidentTimeline incident={incident} />;
});

export default IncidentTimelinePage;

export const generateMetadata = withIncidentMetadata((incident) => {
  return {
    title: `${incident.user_generated_name} — Timeline`,
    description: incident.user_summary || incident.generated_summary,
  };
});
