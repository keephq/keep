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
    <div className="h-full flex flex-col">
      <IncidentHeader incident={incident} />
      <IncidentTabsNavigation incident={incident} />
      <div className="flex-1 min-h-0 overflow-hidden">
        {" "}
        {/* Add overflow-hidden */}
        {AIEnabled ? (
          <ResizableColumns
            leftChild={
              <div className="h-full">
                {" "}
                {/* Remove overflow-hidden */}
                <IncidentChatClientPage
                  mutateIncident={mutate}
                  incident={incident}
                />
              </div>
            }
            rightChild={
              <div className="h-full">
                {" "}
                {/* Remove overflow-hidden */}
                {children}
              </div>
            }
            initialLeftWidth={30}
          />
        ) : (
          <div className="h-full">{children}</div>
        )}
      </div>
    </div>
  );
}
