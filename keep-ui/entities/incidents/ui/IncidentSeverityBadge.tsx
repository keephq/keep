import { Badge } from "@tremor/react";
import { IncidentDto } from "@/app/incidents/models";

import { Icon } from "@tremor/react";
import {
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
} from "@heroicons/react/20/solid";
import { capitalize } from "@/utils/helpers";

interface Props {
  severity: IncidentDto["severity"];
}

export default function IncidentSeverityBadge({ severity }: Props) {
  let icon: any;
  let color: any;
  switch (severity) {
    case "critical":
      icon = ExclamationCircleIcon;
      color = "red";
      break;
    case "warning":
      color = "yellow";
      icon = ExclamationTriangleIcon;
      break;
    case "info":
      icon = InformationCircleIcon;
      color = "green";
      break;
    default:
      icon = InformationCircleIcon;
      color = "blue";
      break;
  }

  return (
    <Badge color={color} className="capitalize" size="sm" icon={icon}>
      {capitalize(severity)}
    </Badge>
  );
}
