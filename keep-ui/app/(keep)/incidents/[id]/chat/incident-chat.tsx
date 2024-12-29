import { CopilotChat, useCopilotChatSuggestions } from "@copilotkit/react-ui";
import type { IncidentDto } from "@/entities/incidents/model";
import { useIncidentAlerts } from "utils/hooks/useIncidents";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { useRouter } from "next/navigation";
import Loading from "@/app/(keep)/loading";
import { useCopilotAction, useCopilotReadable } from "@copilotkit/react-core";
import { Card } from "@tremor/react";
import { useIncidentActions } from "@/entities/incidents/model";
import "@copilotkit/react-ui/styles.css";
import "./incident-chat.css";
import { TraceData, TraceViewer } from "@/shared/ui/TraceViewer";
import { useProviders } from "@/utils/hooks/useProviders";
import { useMemo } from "react";

export function IncidentChat({ incident }: { incident: IncidentDto }) {
  const router = useRouter();
  const { data: alerts, isLoading: alertsLoading } = useIncidentAlerts(
    incident.id
  );
  const { data: providers } = useProviders();

  const providersWithGetTrace = useMemo(
    () =>
      providers?.installed_providers
        .filter(
          (provider) =>
            provider.methods?.some((method) => method.func_name === "get_trace")
        )
        .map((provider) => provider.id),
    [providers]
  );

  const { updateIncident, invokeProviderMethod } = useIncidentActions();

  useCopilotReadable({
    description: "incidentDetails",
    value: incident,
  });
  useCopilotReadable({
    description: "alerts",
    value: alerts?.items,
  });
  useCopilotReadable({
    description: "providersWithGetTrace",
    value: providersWithGetTrace,
  });

  useCopilotChatSuggestions({
    instructions: `The following incident is on going: ${JSON.stringify(
      incident
    )}. Provide good question suggestions for the incident responder team.`,
  });

  useCopilotAction({
    name: "invokeGetTrace",
    description:
      "According to the provided context (provider id and trace id), invoke the get_trace method from the provider",
    parameters: [
      {
        name: "providerId",
        type: "string",
        description: "The ID of the provider to invoke the method on",
      },
      {
        name: "traceId",
        type: "string",
        description: "The trace ID to get the trace for",
      },
    ],
    handler: async ({ providerId, traceId }) => {
      const result = await invokeProviderMethod(providerId, "get_trace", {
        trace_id: traceId,
      });
      return result as any as TraceData;
    },
    render: ({ status, result }) => {
      if (status === "executing" || status === "inProgress") {
        return <Loading />;
      } else if (status === "complete") {
        return <TraceViewer trace={result} />;
      } else {
        return "Trace not found";
      }
    },
  });
  useCopilotAction({
    name: "gotoAlert",
    description: "Select an alert and filter the feed by the alert fingerprint",
    parameters: [
      {
        name: "fingerprint",
        type: "string",
        description:
          "The fingerprint of the alert. You can extract it using the alert name as well.",
        required: true,
      },
    ],
    handler: async ({ fingerprint }) => {
      window.open(`/alerts/feed?fingerprint=${fingerprint}`, "_blank");
    },
  });

  useCopilotAction({
    name: "updateIncidentNameAndSummary",
    description: "Update incident name and summary",
    parameters: [
      {
        name: "name",
        type: "string",
        description: "The new name for the incident",
      },
      {
        name: "summary",
        type: "string",
        description: "The new summary for the incident",
      },
    ],
    handler: async ({ name, summary }) => {
      await updateIncident(
        incident.id,
        {
          user_generated_name: name,
          user_summary: summary,
          assignee: incident.assignee,
          same_incident_in_the_past_id: incident.same_incident_in_the_past_id,
        },
        true
      );
    },
  });

  if (alertsLoading) return <Loading />;
  if (!alerts?.items || alerts.items.length === 0)
    return (
      <EmptyStateCard
        title="Chat not available"
        description="No alerts found for this incident. Go to the alerts feed and assign alerts to interact with the incident."
        buttonText="Assign alerts to this incident"
        onClick={() => router.push("/alerts/feed")}
      />
    );

  return (
    <Card className="h-[calc(100vh-20rem)]">
      <div className="chat-messages">
        <CopilotChat
          className="-mx-2"
          instructions={`You now act as an expert incident responder...`}
          labels={{
            title: "Incident Assistant",
            initial:
              "Hi! 👋 Lets work together to resolve this incident! Ask me anything",
            placeholder:
              "For example: What do you think the root cause of this incident might be?",
          }}
        />
      </div>
    </Card>
  );
}
