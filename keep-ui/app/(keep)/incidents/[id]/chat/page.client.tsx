"use client";

import { IncidentChat } from "./incident-chat";
import { IncidentDto } from "@/entities/incidents/model";
import { EmptyStateCard } from "@/shared/ui";
import { useConfig } from "@/utils/hooks/useConfig";
import { CopilotKit } from "@copilotkit/react-core";
import { ExclamationTriangleIcon } from "@heroicons/react/24/outline";

export function IncidentChatClientPage({
  incident,
}: {
  incident: IncidentDto;
}) {
  const { data: config } = useConfig();

  // If AI is not enabled, return null to collapse the chat section
  if (!config?.OPEN_AI_API_KEY_SET) {
    return null;
  }

  return (
    <CopilotKit showDevConsole={false} runtimeUrl="/api/copilotkit">
      <IncidentChat incident={incident} />
    </CopilotKit>
  );
}
