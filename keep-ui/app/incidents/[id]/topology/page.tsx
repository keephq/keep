import { TopologySearchProvider } from "@/app/topology/TopologySearchContext";
import { TopologyMap } from "@/app/topology/ui/map";
import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";
import { getIncidentName } from "@/entities/incidents/lib/utils";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function IncidentTopologyPage(props: PageProps) {
  const params = await props.params;

  const {
    id
  } = params;

  const incident = await getIncidentWithErrorHandling(id);
  return (
    <main className="h-[calc(100vh-12rem)]">
      <TopologySearchProvider>
        <TopologyMap services={incident.services} />
      </TopologySearchProvider>
    </main>
  );
}

export async function generateMetadata(props: PageProps) {
  const params = await props.params;
  const incident = await getIncidentWithErrorHandling(params.id);
  const incidentName = getIncidentName(incident);
  const incidentDescription =
    incident.user_summary || incident.generated_summary;
  return {
    title: `Keep — ${incidentName} — Topology`,
    description: incidentDescription,
  };
}
