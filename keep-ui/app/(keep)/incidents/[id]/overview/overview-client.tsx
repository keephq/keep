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
    <div className="h-32 bg-gray-50 rounded-lg flex items-center justify-center">
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
    <div className="h-full flex flex-col">
      {/* Metrics section with fixed height */}
      <Card>
        <h3 className="text-lg font-medium mb-4">Metrics</h3>
        <div className="grid grid-cols-3 gap-4">
          <MetricsChart />
          <MetricsChart />
          <MetricsChart />
        </div>
      </Card>

      {/* Alerts section that takes remaining height and scrolls internally */}
      <Card className="flex-1 flex flex-col min-h-0">
        <div className="flex-1 min-h-0">
          <IncidentAlerts incident={incident} />
        </div>
      </Card>
    </div>
  );
}
