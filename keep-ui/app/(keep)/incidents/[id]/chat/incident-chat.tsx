import { CopilotChat, useCopilotChatSuggestions } from "@copilotkit/react-ui";
import type { IncidentDto } from "@/entities/incidents/model";
import { useIncidentAlerts } from "utils/hooks/useIncidents";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { useRouter } from "next/navigation";
import Loading from "@/app/(keep)/loading";
import { useCopilotAction, useCopilotReadable } from "@copilotkit/react-core";
import { Button, Card } from "@tremor/react";
import { useIncidentActions } from "@/entities/incidents/model";
import { TraceData, SimpleTraceViewer } from "@/shared/ui/TraceViewer";
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
  const { updateIncident, invokeProviderMethod, enrichIncident } =
    useIncidentActions();
  const providersWithGetTrace = useMemo(
    () =>
      providers?.installed_providers.filter(
        (provider) =>
          provider.methods?.some((method) => method.func_name === "get_trace")
      ),
    [providers]
  );

  // Suggestions
  useCopilotChatSuggestions(
    {
      instructions: "Suggest the most relevant next actions.",
    },
    [incident, alerts, providersWithGetTrace]
  );

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
  useCopilotReadable({
    description:
      "The installed providers and the methods you can invoke using invokeProviderMethod",
    value: providers?.installed_providers,
  });

  // Actions
  useCopilotAction({
    name: "invokeProviderMethod",
    description:
      "Invoke a method from a provider. The method is invoked on the provider with the given id and the parameters are the ones provided in the parameters object.",
    parameters: [
      {
        name: "providerId",
        type: "string",
        description: "The ID of the provider to invoke the method on",
      },
      {
        name: "methodName",
        type: "string",
        description: "The name of the method to invoke",
      },
      {
        name: "methodParams",
        type: "object",
        description:
          "The parameters the method expects as described in func_params",
      },
    ],
    handler: async ({ providerId, methodName, methodParams }) => {
      const result = await invokeProviderMethod(
        providerId,
        methodName,
        methodParams as { [key: string]: string }
      );
      return result;
    },
  });
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
      if (
        incident.enrichments &&
        incident.enrichments["traces"] &&
        incident.enrichments["traces"][traceId]
      ) {
        return incident.enrichments["traces"][traceId] as TraceData;
      }

      const result = await invokeProviderMethod(providerId, "get_trace", {
        trace_id: traceId,
      });

      if (typeof result !== "string") {
        const existingTraces = incident.enrichments["traces"] || {};
        await enrichIncident(incident.id, {
          traces: {
            ...existingTraces,
            [traceId]: result,
          },
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
        return <SimpleTraceViewer trace={result} />;
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
            instructions="You now act as an expert incident responder..."
            labels={{
              title: "Incident Assistant",
              initial:
                "Hi! 👋 Lets work together to resolve this incident! Ask me anything",
              placeholder: "For example: Find the root cause of this incident",
            }}
          />
        </div>
      </div>
    </Card>
  );
}
