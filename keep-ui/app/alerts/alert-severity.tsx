import { Icon } from "@tremor/react";
import { Severity } from "./models";
import {
  ArrowDownIcon,
  ArrowDownRightIcon,
  ArrowRightIcon,
  ArrowUpIcon,
  ArrowUpRightIcon,
} from "@heroicons/react/24/outline";

interface Props {
  severity: Severity | undefined;
}

export default function AlertSeverity({ severity }: Props) {
  let icon: any;
  let color: any;
  let severityText: string;
  switch (severity) {
    case "critical":
      icon = ArrowUpIcon;
      color = "red";
      severityText = Severity.Critical.toString();
      break;
    case "high":
      icon = ArrowRightIcon;
      color = "orange";
      severityText = Severity.High.toString();
      break;
    case "error":
      icon = ArrowUpRightIcon;
      color = "orange";
      severityText = Severity.High.toString();
      break;
    case "warning":
      color = "yellow";
      icon = ArrowRightIcon;
      severityText = Severity.Warning.toString();
      break;
    case "low":
      icon = ArrowDownRightIcon;
      color = "green";
      severityText = Severity.Low.toString();
      break;
    default:
      icon = ArrowDownIcon;
      color = "emerald";
      severityText = Severity.Info.toString();
      break;
  }

  return (
    <Icon
      //deltaType={deltaType as DeltaType}
      color={color}
      icon={icon}
      tooltip={severityText}
      size="sm"
      className="ml-2.5"
    />
  );
}
