import { TopologySearchProvider } from "@/app/topology/TopologySearchContext";
import { TopologyMap } from "@/app/topology/ui/map";
import { withIncident, withIncidentMetadata } from "../withIncident";

const IncidentTopologyPage = withIncident(function _IncidentTopologyPage({
  incident,
}) {
  return (
    <main className="pt-3 h-[calc(100vh-12rem)]">
      <TopologySearchProvider>
        <TopologyMap services={incident.services} />
      </TopologySearchProvider>
    </main>
  );
});

export default IncidentTopologyPage;

export const generateMetadata = withIncidentMetadata((incident) => {
  return {
    title: `${incident.user_generated_name} — Topology`,
    description: incident.user_summary || incident.generated_summary,
  };
});
