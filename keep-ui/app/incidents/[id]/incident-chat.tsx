import { CopilotChat } from "@copilotkit/react-ui";
import { IncidentDto } from "../models";
import { useIncidentAlerts } from "utils/hooks/useIncidents";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { useRouter } from "next/navigation";
import "./incident-chat.css";
import Loading from "app/loading";

export default function IncidentChat({ incident }: { incident: IncidentDto }) {
  const router = useRouter();
  const { data: alerts, isLoading: alertsLoading } = useIncidentAlerts(
    incident.id
  );

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
    <CopilotChat
      className="h-full overflow-y-hidden"
      instructions={`You are an expert incident responder.
      You are responsible for resolving incidents and helping the incident responder team.
      The information you are provided with is a JSON representing all the data about the incident and a list of alerts that are related to the incident.
      Your job is to help the incident responder team to resolve the incident by providing insights and recommendations.

      If you are not sure about the answer, you NEED to say you don't know and lack more context.

      Here is the incident JSON with all the details: "${JSON.stringify(
        incident
      )}"
      Here is the list of alerts related to the incident: "${JSON.stringify(
        alerts.items
      )}"`}
      labels={{
        title: "Incident Assitant",
        initial:
          "Hi! 👋 Lets work together to resolve thins incident! What can I help you with?",
        placeholder:
          "What do you think the root cause of this incident might be?",
      }}
    />
  );
}
