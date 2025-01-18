"use client";

import { ReactNode } from "react";
import { IncidentDto } from "@/entities/incidents/model";
import { IncidentChatClientPage } from "./chat/page.client";
import { useIncident } from "@/utils/hooks/useIncidents";
import { IncidentHeader } from "./incident-header";
import { IncidentTabsNavigation } from "./incident-tabs-navigation";
import ResizableColumns from "@/components/ui/ResizableColumns";

export function IncidentLayoutClient({
  children,
  initialIncident,
  AIEnabled,
}: {
  children: ReactNode;
  initialIncident: IncidentDto;
  AIEnabled: boolean;
}) {
  const { data: incident, mutate } = useIncident(initialIncident.id, {
    fallbackData: initialIncident,
  });

  if (!incident) {
    return null;
  }

  return (
    <div className="flex flex-col gap-4">
      <IncidentHeader incident={incident} />
      <IncidentTabsNavigation incident={incident} />
      {AIEnabled ? (
        <ResizableColumns
          leftChild={
            <div className="pr-2">
              <div className="flex-1 min-w-0">{children}</div>
            </div>
          }
          rightChild={
            <div className="pl-2">
              <IncidentChatClientPage
                mutateIncident={mutate}
                incident={incident}
              />
            </div>
          }
          initialLeftWidth={60}
        />
      ) : (
        <div className="flex-1 min-w-0">{children}</div>
      )}
    </div>
  );
}
