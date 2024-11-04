import { TopologySearchProvider } from "@/app/topology/TopologySearchContext";
import { TopologyMap } from "@/app/topology/ui/map";
import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";

type PageProps = {
  params: { id: string };
};

export default async function IncidentTopologyPage({
  params: { id },
}: PageProps) {
  const incident = await getIncidentWithErrorHandling(id);
  return (
    <main className="pt-3 h-[calc(100vh-12rem)]">
      <TopologySearchProvider>
        <TopologyMap services={incident.services} />
      </TopologySearchProvider>
    </main>
  );
}

export async function generateMetadata({ params }: PageProps) {
  const incident = await getIncidentWithErrorHandling(params.id);
  const incidentName =
    incident.user_generated_name || incident.ai_generated_name;
  const incidentDescription =
    incident.user_summary || incident.generated_summary;
  return {
    title: `${incidentName} — Topology`,
    description: incidentDescription,
  };
}
