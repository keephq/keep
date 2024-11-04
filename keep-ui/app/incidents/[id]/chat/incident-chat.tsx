import {
  CopilotChat,
  CopilotKitCSSProperties,
  useCopilotChatSuggestions,
} from "@copilotkit/react-ui";
import type { IncidentDto } from "@/entities/incidents/model";
import { useIncidentAlerts } from "utils/hooks/useIncidents";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { useRouter } from "next/navigation";
import Loading from "app/loading";
import { useCopilotAction, useCopilotReadable } from "@copilotkit/react-core";
import { Card } from "@tremor/react";
import { useIncidentActions } from "@/entities/incidents/model";
import "@copilotkit/react-ui/styles.css";
import "./incident-chat.css";

export function IncidentChat({ incident }: { incident: IncidentDto }) {
  const router = useRouter();
  const { data: alerts, isLoading: alertsLoading } = useIncidentAlerts(
    incident.id
  );

  const { updateIncident } = useIncidentActions();

  useCopilotReadable({
    description: "incidentDetails",
    value: incident,
  });
  useCopilotReadable({
    description: "alerts",
    value: alerts?.items,
  });

  useCopilotChatSuggestions({
    instructions: `The following incident is on going: ${JSON.stringify(
      incident
    )}. Provide good question suggestions for the incident responder team.`,
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
    <Card>
      <div
        style={
          {
            "--copilot-kit-primary-color":
              "rgb(249 115 22 / var(--tw-bg-opacity))",
          } as CopilotKitCSSProperties
        }
        className="max-w-3xl mx-auto"
      >
        <CopilotChat
          className="-mx-2"
          instructions={`You now act as an expert incident responder.
      You are responsible for resolving incidents and helping the incident responding team.
      The information you are provided with is a JSON representing all the data about the incident and a list of alerts that are related to the incident.
      Your job is to help the incident responder team to resolve the incident as soon as possible by providing insights and recommendations.

      Use the incident details and alerts context to give good, meaningful answers.
      If you do not know the answer or lack context, share that with the end user and ask for more context.`}
          labels={{
            title: "Incident Assitant",
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
