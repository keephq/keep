import { AlertDto, Severity, Status } from "@/app/alerts/models";
import { IncidentDto } from "../models";

const mockActivities: {
  id: number;
  type: "comment" | "alert";
  text: string;
  timestamp: Date;
  initiator: string | AlertDto;
}[] = [
  {
    id: 1,
    type: "comment",
    text: "This is a wonderful first comment!",
    timestamp: new Date(),
    initiator: "Olivia Martin",
  },
  {
    id: 2,
    type: "alert",
    text: "",
    timestamp: new Date(),
    initiator: {
      id: "alert-1",
      event_id: "asdf",
      name: "High CPU Usage Alert",
      status: Status.Firing,
      lastReceived: new Date(),
      environment: "production",
      source: ["splunk"],
      message: "CPU usage has exceeded 90%",
      severity: Severity.High,
      url: "http://example.com/alert/1",
      service: "backend-service",
      pushed: false,
      fingerprint: "fingerprint-1",
      deleted: false,
      dismissed: false,
      ticket_url: "http://example.com/ticket/1",
      enriched_fields: [],
    },
  },
];

export default function IncidentActivity(incident: { incident: IncidentDto }) {
  return <>Activity!</>;
}
