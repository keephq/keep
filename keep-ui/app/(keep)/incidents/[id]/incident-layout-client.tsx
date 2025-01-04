"use client";

import { ReactNode } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { IncidentDto } from "@/entities/incidents/model";
import { IncidentChatClientPage } from "./chat/page.client";
import { useIncident } from "@/utils/hooks/useIncidents";
import { IncidentHeader } from "./incident-header";
import { IncidentTabsNavigation } from "./incident-tabs-navigation";

function ResizeHandle() {
  return (
    <PanelResizeHandle className="w-2 group hover:bg-tremor-brand-subtle transition-colors">
      <div className="h-full w-1 mx-auto bg-tremor-border group-hover:bg-tremor-brand group-hover:w-1.5 transition-all" />
    </PanelResizeHandle>
  );
}

export function IncidentLayoutClient({
  children,
  initialIncident,
  AIEnabled,
}: {
  children: ReactNode;
  initialIncident: IncidentDto;
  AIEnabled: boolean;
}) {
  const { data: incident } = useIncident(initialIncident.id, {
    fallbackData: initialIncident,
  });

  if (!incident) {
    return null;
  }

  return (
    <div className="flex flex-col gap-4">
      <IncidentHeader incident={incident} />
      <IncidentTabsNavigation incident={incident} />
      <PanelGroup direction="horizontal">
        <Panel defaultSize={60} minSize={30}>
          <div className="pr-2">
            <div className="flex-1 min-w-0">{children}</div>
          </div>
        </Panel>
        {AIEnabled && (
          <>
            <ResizeHandle />
            <Panel defaultSize={40} minSize={25}>
              <div className="pl-2">
                <IncidentChatClientPage incident={incident} />
              </div>
            </Panel>
          </>
        )}
      </PanelGroup>
    </div>
  );
}
