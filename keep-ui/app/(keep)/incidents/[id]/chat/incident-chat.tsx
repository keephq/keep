import { CopilotChat, useCopilotChatSuggestions } from "@copilotkit/react-ui";
import type { IncidentDto } from "@/entities/incidents/model";
import { useIncidentAlerts } from "utils/hooks/useIncidents";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { useRouter } from "next/navigation";
import Loading from "@/app/(keep)/loading";
import {
  CopilotTask,
  useCopilotAction,
  useCopilotContext,
  useCopilotReadable,
} from "@copilotkit/react-core";
import { Button, Card } from "@tremor/react";
import { useIncidentActions } from "@/entities/incidents/model";
import { TraceData, TraceViewer } from "@/shared/ui/TraceViewer";
import { useProviders } from "@/utils/hooks/useProviders";
import { useMemo } from "react";
import "@copilotkit/react-ui/styles.css";
import "./incident-chat.css";

export function IncidentChat({ incident }: { incident: IncidentDto }) {
  const router = useRouter();
  const { data: alerts, isLoading: alertsLoading } = useIncidentAlerts(
    incident.id
  );
  const { data: providers } = useProviders();
  const context = useCopilotContext();

  const providersWithGetTrace = useMemo(
    () =>
      providers?.installed_providers.filter(
        (provider) =>
          provider.methods?.some((method) => method.func_name === "get_trace")
      ),
    [providers]
  );

  const { updateIncident, invokeProviderMethod, enrichIncident } =
    useIncidentActions();

  // Suggestions
  useCopilotChatSuggestions({
    instructions: `The following incident is on going: ${JSON.stringify(
      incident
    )}. Provide good question suggestions for the incident responder team.`,
  });

  // Chat context
  useCopilotReadable({
    description: "incidentDetails",
    value: incident,
  });
  useCopilotReadable({
    description: "alerts",
    value: alerts?.items,
  });
  useCopilotReadable({
    description: "The providers you can get traces from",
    value: providersWithGetTrace,
  });

  // Actions
  useCopilotAction({
    name: "invokeGetTrace",
    description:
      "According to the provided context (provider id and trace id), invoke the get_trace method from the provider. If the alerts already contain trace_id or traceId and the type of the provider is available, automatically get that trace. If the trace is available in the incident enrichments, use it and mention that it was previously fetched.",
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
      if (incident.enrichments && incident.enrichments[traceId]) {
        return incident.enrichments[traceId] as TraceData;
      }

      const result = await invokeProviderMethod(providerId, "get_trace", {
        trace_id: traceId,
      });

      if (typeof result !== "string") {
        await enrichIncident(incident.id, {
          [traceId]: result,
        });
      }

      return result as TraceData;
    },
    render: ({ status, result }) => {
      if (status === "executing" || status === "inProgress") {
        return (
          <Button color="slate" size="lg" disabled loading>
            Loading...
          </Button>
        );
      } else if (status === "complete" && typeof result !== "string") {
        return <TraceViewer trace={result} />;
      } else {
        return <Card>Trace not found: {result}</Card>;
      }
    },
  });

  useCopilotAction({
    name: "updateIncidentNameAndSummary",
    description:
      "Update incident name and summary, if the user asked you to update just one of them, update only that one",
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

  if (alertsLoading || !incident) return <Loading />;
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
    <Card className="max-h-[calc(100vh-28rem)]">
      <div className="chat-container">
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
      </div>
    </Card>
  );
}
