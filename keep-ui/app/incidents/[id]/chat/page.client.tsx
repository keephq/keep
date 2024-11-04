"use client";

import { IncidentChat } from "./incident-chat";
import { IncidentDto } from "@/entities/incidents/model";
import { CopilotKit } from "@copilotkit/react-core";

export function IncidentChatClientPage({
  incident,
}: {
  incident: IncidentDto;
}) {
  return (
    <CopilotKit runtimeUrl="/api/copilotkit">
      <IncidentChat incident={incident} />
    </CopilotKit>
  );
}
