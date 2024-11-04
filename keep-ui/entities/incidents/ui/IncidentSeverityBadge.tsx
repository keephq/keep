import { Badge, BadgeProps } from "@tremor/react";
import { IncidentDto } from "@/entities/incidents/model";

import {
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
} from "@heroicons/react/20/solid";
import { capitalize } from "@/utils/helpers";

interface Props {
  severity: IncidentDto["severity"];
  size?: BadgeProps["size"];
}

export function IncidentSeverityBadge({ severity, size = "xs" }: Props) {
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

  return (
    <Badge color={color} className="capitalize" size={size} icon={icon}>
      {capitalize(severity)}
    </Badge>
  );
}
