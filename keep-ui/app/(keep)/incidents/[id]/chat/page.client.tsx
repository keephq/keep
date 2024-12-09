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
  if (config && !config.OPEN_AI_API_KEY_SET) {
    return (
      <EmptyStateCard
        icon={ExclamationTriangleIcon}
        title="Chat is not available"
        description="The OpenAI API key is not set. Ask your administrator to set it to enable chat."
      />
    );
  }

  return (
    <CopilotKit runtimeUrl="/api/copilotkit">
      <IncidentChat incident={incident} />
    </CopilotKit>
  );
}
