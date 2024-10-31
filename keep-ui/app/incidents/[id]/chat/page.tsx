import { IncidentChatClientPage } from "./page.client";
import { withIncident, withIncidentMetadata } from "../withIncident";

const IncidentChatPage = withIncident(function _IncidentChatPage({ incident }) {
  return <IncidentChatClientPage incident={incident} />;
});

export default IncidentChatPage;

export const generateMetadata = withIncidentMetadata((incident) => {
  return {
    title: `${incident.user_generated_name} — Chat with AI`,
    description: incident.user_summary || incident.generated_summary,
  };
});
