import { Badge, BadgeProps } from "@tremor/react";
import { Status } from "@/entities/incidents/model";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  PauseIcon,
} from "@heroicons/react/24/outline";
import { IoIosGitPullRequest } from "react-icons/io";
import { capitalize } from "@/utils/helpers";

interface Props {
  status: Status;
  size?: BadgeProps["size"];
}

export function IncidentStatusBadge({ status, size = "xs" }: Props) {
  let icon: any;
  let color: any;

  switch (status) {
    case Status.Firing:
      icon = ExclamationCircleIcon;
      color = "red";
      break;
    case Status.Resolved:
      icon = CheckCircleIcon;
      color = "green";
      break;
    case Status.Acknowledged:
      icon = PauseIcon;
      color = "gray";
      break;
    case Status.Merged:
      icon = IoIosGitPullRequest;
      color = "purple";
      break;
    default:
      icon = ExclamationCircleIcon;
      color = "gray";
      break;
  }

  return (
    <Badge
      color={color}
      className="capitalize rounded-full"
      size={size}
      icon={icon}
    >
      {capitalize(status)}
    </Badge>
  );
}
