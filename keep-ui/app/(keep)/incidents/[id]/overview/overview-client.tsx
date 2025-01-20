// keep-ui/app/(keep)/incidents/[id]/overview/overview-client.tsx
"use client";

import React from "react";
import { Card } from "@tremor/react";
import { IncidentDto } from "@/entities/incidents/model";
import IncidentAlerts from "../alerts/incident-alerts";
import { useIncident } from "@/utils/hooks/useIncidents";

// Placeholder chart component
function MetricsChart() {
  return (
    <div className="h-48 bg-gray-50 rounded-lg flex items-center justify-center">
      <span className="text-gray-400">Metrics visualization placeholder</span>
    </div>
  );
}

export default function OverviewClientPage({
  initialIncident,
}: {
  initialIncident: IncidentDto;
}) {
  const { data: incident, mutate } = useIncident(initialIncident.id, {
    fallbackData: initialIncident,
  });

  if (!incident) return null;

  return (
    <div className="flex flex-col gap-6 h-[calc(100vh-15rem)]">
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
          <div className="h-[calc(100%-3rem)] overflow-hidden">
            <IncidentAlerts incident={incident} />
          </div>
        </Card>
      </div>
    </div>
  );
}
