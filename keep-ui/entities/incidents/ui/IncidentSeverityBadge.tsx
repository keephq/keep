import { Badge, BadgeProps } from "@tremor/react";
import { IncidentDto } from "@/entities/incidents/model";

import {
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
} from "@heroicons/react/20/solid";
import { capitalize } from "@/utils/helpers";
import {getIncidentSeverityIconAndColor} from "@/entities/incidents/lib/utils";

interface Props {
  severity: IncidentDto["severity"];
  size?: BadgeProps["size"];
}

export function IncidentSeverityBadge({ severity, size = "xs" }: Props) {
  const {icon, color} = getIncidentSeverityIconAndColor(severity);

  return (
    <Badge color={color} className="capitalize" size={size} icon={icon}>
      {capitalize(severity)}
    </Badge>
  );
}
