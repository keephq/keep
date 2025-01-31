import { Icon } from "@tremor/react";
import { Severity } from "@/entities/alerts/model";
import {
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
} from "@heroicons/react/20/solid";
import { capitalize } from "@/utils/helpers";

interface Props {
  severity: Severity | undefined;
}

export default function AlertSeverity({ severity }: Props) {
  let icon: any;
  let color: any;
  let severityText: string;
  switch (severity) {
    case "critical":
      icon = ExclamationCircleIcon;
      color = "red";
      severityText = Severity.Critical.toString();
      break;
    case "high":
      icon = ExclamationCircleIcon;
      color = "orange";
      severityText = Severity.High.toString();
      break;
    case "error":
      icon = ExclamationTriangleIcon;
      color = "orange";
      severityText = Severity.High.toString();
      break;
    case "warning":
      color = "yellow";
      icon = ExclamationTriangleIcon;
      severityText = Severity.Warning.toString();
      break;
    case "low":
      icon = InformationCircleIcon;
      color = "green";
      severityText = Severity.Low.toString();
      break;
    default:
      icon = InformationCircleIcon;
      color = "blue";
      severityText = Severity.Info.toString();
      break;
  }

  return (
    <Icon
      color={color}
      icon={icon}
      tooltip={capitalize(severityText)}
      size="sm"
      className="!p-0"
    />
  );
}
