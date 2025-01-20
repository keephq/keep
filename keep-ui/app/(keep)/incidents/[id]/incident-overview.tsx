import React from "react";
import { Card } from "@tremor/react";
import { IncidentDto } from "@/entities/incidents/model";
import { IncidentChatClientPage } from "./chat/page.client";
import IncidentAlerts from "./alerts/incident-alerts";

// Placeholder chart component
function MetricsChart() {
  return (
    <div className="h-48 bg-gray-50 rounded-lg flex items-center justify-center">
      <span className="text-gray-400">Metrics visualization placeholder</span>
    </div>
  );
}

export default function OverviewPage({
  incident,
  mutateIncident,
}: {
  incident: IncidentDto;
  mutateIncident: () => void;
}) {
  return (
    <div className="flex gap-6 h-[calc(100vh-15rem)]">
      {/* Left side - Chat */}
      <div className="w-1/3 flex flex-col">
        <Card className="flex-1 overflow-hidden">
          <div className="h-full">
            <IncidentChatClientPage
              incident={incident}
              mutateIncident={mutateIncident}
            />
          </div>
        </Card>
      </div>

      {/* Right side - Split view with Metrics and Alerts */}
      <div className="w-2/3 flex flex-col gap-6">
        {/* Metrics Charts - Top section */}
        <div className="h-1/2">
          <Card className="h-full">
            <h3 className="text-lg font-medium mb-4">Metrics</h3>
            <div className="grid grid-cols-2 gap-4 h-[calc(100%-3rem)]">
              <MetricsChart />
              <MetricsChart />
              <MetricsChart />
              <MetricsChart />
            </div>
          </Card>
        </div>

        {/* Alerts Table - Bottom section */}
        <div className="h-1/2">
          <Card className="h-full overflow-hidden">
            <h3 className="text-lg font-medium mb-4">Related Alerts</h3>
            <div className="h-[calc(100%-3rem)] overflow-hidden">
              <IncidentAlerts incident={incident} />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
