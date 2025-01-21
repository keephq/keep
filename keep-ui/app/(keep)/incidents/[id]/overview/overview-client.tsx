"use client";

import React from "react";
import { Card } from "@tremor/react";
import { IncidentDto } from "@/entities/incidents/model";
import IncidentAlerts from "../alerts/incident-alerts";
import { useIncident } from "@/utils/hooks/useIncidents";
import { MetadataCard } from "./components/MetadataCard";
import { AlertTimeline } from "./components/AlertTimeline";
import { MetricsRadar } from "./components/MetricsRadar";

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
    <div className="h-full flex flex-col space-y-4">
      {/* Metrics section with three cards */}
      <div className="grid grid-cols-3 gap-4 h-96">
        <Card className="h-full overflow-hidden">
          <MetadataCard incident={incident} />
        </Card>
        <Card className="h-full overflow-hidden">
          <div className="h-full flex flex-col">
            <h3 className="text-sm text-gray-500 mb-4">EVENT TIMELINE</h3>
            <div className="flex-1">
              <AlertTimeline />
            </div>
            <button className="mt-4 text-sm text-gray-500">
              See whole incident timeline
            </button>
          </div>
        </Card>
        <Card className="h-full overflow-hidden">
          <div className="h-full flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-sm text-gray-500">ACCURACY SCORE</h3>
              <span className="text-2xl font-semibold">68</span>
            </div>
            <div className="flex-1">
              <MetricsRadar />
            </div>
          </div>
        </Card>
      </div>

      {/* Alerts section that takes remaining height and scrolls internally */}
      <Card className="flex-1 flex flex-col min-h-0">
        <div className="flex-1 min-h-0">
          <IncidentAlerts incident={incident} />
        </div>
      </Card>
    </div>
  );
}
