import { IncidentDto } from "@/entities/incidents/model";
import {ExclamationCircleIcon, ExclamationTriangleIcon, InformationCircleIcon} from "@heroicons/react/20/solid";

export function getIncidentName(incident: IncidentDto) {
  return (
    incident.user_generated_name || incident.ai_generated_name || incident.id
  );
}


export function getIncidentSeverityIconAndColor(severity: IncidentDto["severity"]) {
  let icon: any;
  let color: any;

  switch (severity) {
    case "critical":
      icon = ExclamationCircleIcon;
      color = "red";
      break;
    case "high":
      icon = ExclamationTriangleIcon;
      color = "orange";
      break;
    case "warning":
      color = "yellow";
      icon = ExclamationTriangleIcon;
      break;
    case "info":
      icon = InformationCircleIcon;
      color = "green";
      break;
    case "low":
      icon = InformationCircleIcon;
      color = "blue";
      break;
    default:
      icon = InformationCircleIcon;
      color = "blue";
      break;
  }
  return {icon, color}
}
