"use client";

import { IncidentChat } from "./incident-chat";
import { IncidentDto } from "@/entities/incidents/model";
import { useConfig } from "@/utils/hooks/useConfig";
import { CopilotKit } from "@copilotkit/react-core";

export function IncidentChatClientPage({
  incident,
  mutateIncident,
}: {
  incident: IncidentDto;
  mutateIncident: () => void;
}) {
  const { data: config } = useConfig();

  // If AI is not enabled, return null to collapse the chat section
  if (!config?.OPEN_AI_API_KEY_SET) {
    return null;
  }

  return (
    <CopilotKit showDevConsole={false} runtimeUrl="/api/copilotkit">
      <IncidentChat incident={incident} mutateIncident={mutateIncident} />
    </CopilotKit>
  );
}
