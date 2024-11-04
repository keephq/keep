import { IncidentDto } from "@/app/incidents/models";

export function getIncidentName(incident: IncidentDto) {
  return (
    incident.user_generated_name || incident.ai_generated_name || incident.id
  );
}
