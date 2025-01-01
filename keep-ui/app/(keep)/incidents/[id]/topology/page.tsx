import { TopologySearchProvider } from "@/app/(keep)/topology/TopologySearchContext";
import { TopologyMap } from "@/app/(keep)/topology/ui/map";
import { getIncidentWithErrorHandling } from "../getIncidentWithErrorHandling";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import { TopologyApplication } from "@/app/(keep)/topology/model";
import { getApplications } from "@/app/(keep)/topology/api";
import { createServerApiClient } from "@/shared/api/server";

type PageProps = {
  params: { id: string };
};

export default async function IncidentTopologyPage({
  params: { id },
}: PageProps) {
  let initialApplications: TopologyApplication[] = [];

  const api = await createServerApiClient();
  const incident = await getIncidentWithErrorHandling(id);
  const applications = await getApplications(api);

  // if this is topology-based incident, we want to show only the application
  // that is related to the incident
  if (incident.incident_type === "topology" && incident.incident_application) {
    const relevantApplication = applications.find(
      (app) => app.id === incident.incident_application
    );

    return (
      <main className="h-[calc(100vh-12rem)]">
        <TopologySearchProvider>
          <TopologyMap
            selectedApplicationIds={[relevantApplication?.id || ""]}
            topologyApplications={applications}
          />
        </TopologySearchProvider>
      </main>
    );
  } else {
    return (
      <main className="h-[calc(100vh-12rem)]">
        <TopologySearchProvider>
          <TopologyMap services={incident.services} />
        </TopologySearchProvider>
      </main>
    );
  }
}

export async function generateMetadata({ params }: PageProps) {
  const incident = await getIncidentWithErrorHandling(params.id);
  const incidentName = getIncidentName(incident);
  const incidentDescription =
    incident.user_summary || incident.generated_summary;
  return {
    title: `Keep — ${incidentName} — Topology`,
    description: incidentDescription,
  };
}
